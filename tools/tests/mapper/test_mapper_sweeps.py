#!/usr/bin/env python3
"""A sweep is a recall device over the unaccounted pile, and a sweep that examined nothing is not
a pass.

`requiredSweeps` declared eleven completeness challenges and nothing ran any of them (#250).
Five things are watched here, because each is a way this tool could report a completeness it did
not measure:

  * a sweep finds an **unaccounted** unit that looks like it states a rule of its kind, and does
    **not** report a unit the walk already reached -- the candidate set is what separates this
    from the corpus-wide phrase scan #208 measured as blind;
  * a required sweep the registry does not implement is reported **by name** and exits NOT
    VERIFIED, never skipped: that is the standing rule that let `requiredSweeps` exist before any
    sweep did;
  * a sweep whose cues fire on no unaccounted unit **and** on no unit the walk reached is a dead
    cue list and fails, unless the protocol declares why -- and a declared reason a live cue
    contradicts fails too;
  * `extent-coverage` delegates to the inventory rather than measuring coverage a second time,
    and is the one sweep a zero is a pass for;
  * `cross-references` does not count a unit naming its own section, which 0009 already refuses
    as a pointer and which would otherwise fire on every heading of a designated corpus.

The six committed maps are then run through it, because a checker nobody has watched over real
corpora is one that has only ever seen its own fixtures.

Run: python3 -m unittest discover -s tools/tests -t tools
"""
import glob
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
REPO = os.path.dirname(TOOLS)

sys.path.insert(0, TOOLS)
try:
    from mapper import cli, protocol, sweeps
finally:
    sys.path.remove(TOOLS)

NOT_VERIFIED = 3

# Four blocks on one page. Block 1 is quoted by the map, so the walk reaches it; blocks 2, 3 and
# 4 are unaccounted, and each is the candidate for one sweep. Block 2 states an exception the map
# does not hold, block 3 a permission, block 4 nothing any built-in cue fires on.
FIXTURE = """{8} A page before the extent, stating nothing this map claims.

{9} A player who is on the bar must enter before moving any other man.

A man may not be borne off unless every man is in the home table.

A player may double the stake at any time before throwing.

The board is laid out with thirty men, fifteen of each colour.
"""


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue() + err.getvalue()


def maps():
    found = sorted(glob.glob(os.path.join(REPO, "examples", "*", "corpus-map*.json")))
    found += sorted(glob.glob(os.path.join(REPO, "examples", "*", "*", "corpus-map*.json")))
    return found


class Fixture:
    """A map, a manifest, a protocol and a corpus in a directory of this test's own."""

    def __init__(self, required=("exceptions", "permissions"), **protocol_extra):
        self.directory = tempfile.mkdtemp(prefix="sweeps-test-")
        with open(os.path.join(self.directory, "corpus.txt"), "w", encoding="utf-8") as handle:
            handle.write(FIXTURE)
        self.map_path = os.path.join(self.directory, "corpus-map.json")
        self.write("corpus-manifest.json", {
            "schemaVersion": 1,
            "corpora": [{"sourceId": "fixture", "adapter": "plain-text",
                         "committedPath": "corpus.txt", "verification": "committed-copy"}],
        })
        self.write("corpus-map.json", {
            "schemaVersion": 1, "corpus": "fixture", "baseline": "fixture",
            "extent": {"unit": "page", "from": 9, "to": 9},
            "entries": [{"id": "enter-from-the-bar", "evidence":
                         "A player who is on the bar must enter before moving any other man."}],
        })
        self.protocol(required, **protocol_extra)

    def protocol(self, required, **extra):
        document = {
            "protocolVersion": 1, "corpus": "fixture", "units": ["paragraph"],
            "pointerMechanisms": [{"mechanism": "phrase"}],
            "requiredSweeps": list(required),
            "adapterReach": {"text": "readable"},
        }
        document.update(extra)
        self.write("mapping-protocol.json", document)

    def write(self, name, document):
        with open(os.path.join(self.directory, name), "w", encoding="utf-8") as handle:
            json.dump(document, handle)

    def remove(self):
        shutil.rmtree(self.directory)


class TestASweepFindsWhatTheWalkDidNotAccountFor(unittest.TestCase):
    def setUp(self):
        self.fixture = Fixture()
        self.addCleanup(self.fixture.remove)

    def test_an_unaccounted_unit_of_the_sweeps_kind_is_a_finding(self):
        code, out = run(["sweeps", self.fixture.map_path])
        self.assertEqual(code, NOT_VERIFIED, out)
        self.assertIn("exceptions: 1 finding(s) in 3 candidate unit(s)", out)
        self.assertIn("p. 9 block 2", out)

    def test_a_unit_the_walk_reached_is_not_a_finding(self):
        """The whole difference from #208's phrase scan. Block 1 is quoted by an entry, so it is
        accounted for and cannot be a finding, however many cues it matches."""
        self.fixture.write("corpus-map.json", {
            "schemaVersion": 1, "corpus": "fixture", "baseline": "fixture",
            "extent": {"unit": "page", "from": 9, "to": 9},
            "entries": [{"id": "bear-off", "evidence":
                         "A man may not be borne off unless every man is in the home table."}],
        })
        code, out = run(["sweeps", self.fixture.map_path])
        self.assertEqual(code, NOT_VERIFIED, out)
        self.assertIn("exceptions: 0 finding(s) in 3 candidate unit(s), and 1 accounted unit(s)",
                      out)
        self.assertNotIn("?  p. 9 block 2", out)

    def test_a_declared_cue_fires_where_the_built_in_list_does_not(self):
        """0026's shape: a corpus's own cues are read in addition to the built-in list."""
        before, _ = run(["sweeps", self.fixture.map_path])
        self.fixture.protocol(("exceptions", "permissions"),
                              sweepCues={"permissions": ["is laid out with"]})
        code, out = run(["sweeps", self.fixture.map_path])
        self.assertEqual((before, code), (NOT_VERIFIED, NOT_VERIFIED), out)
        self.assertIn("permissions: 2 finding(s)", out)
        self.assertIn("p. 9 block 4", out)


class TestASweepTheMapperCannotRunIsReportedByName(unittest.TestCase):
    """A protocol naming a sweep nothing implements must not read as a pass. It is the reason the
    declaration was allowed to exist before the implementation."""

    def setUp(self):
        self.fixture = Fixture()
        self.addCleanup(self.fixture.remove)
        self.retired = sweeps.REGISTRY.pop("permissions")
        self.addCleanup(lambda: sweeps.REGISTRY.__setitem__("permissions", self.retired))

    def test_it_is_named_and_the_run_is_not_verified(self):
        code, out = run(["sweeps", self.fixture.map_path])
        self.assertEqual(code, NOT_VERIFIED, out)
        self.assertIn("NOT IMPLEMENTED  permissions", out)
        self.assertIn("not implemented -- permissions", out)

    def test_the_protocol_command_names_it_too(self):
        code, out = run(["protocol", self.fixture.map_path])
        self.assertEqual(code, 0, out)
        self.assertIn("NOT IMPLEMENTED: permissions", out)

    def test_every_sweep_of_the_closed_set_is_implemented_today(self):
        sweeps.REGISTRY["permissions"] = self.retired
        self.assertEqual(sorted(sweeps.REGISTRY), sorted(protocol.SWEEPS))


class TestASilentZeroIsNotAPass(unittest.TestCase):
    def setUp(self):
        self.fixture = Fixture(required=("definitions", "exceptions"))
        self.addCleanup(self.fixture.remove)

    def test_a_sweep_that_fires_nowhere_in_the_extent_fails(self):
        code, out = run(["sweeps", self.fixture.map_path])
        self.assertEqual(code, 1, out)
        self.assertIn("X  definitions", out)
        self.assertIn("fired on no accounted unit of the extent either", out)

    def test_a_declared_reason_accounts_for_it(self):
        self.fixture.protocol(("definitions", "exceptions"), sweepCuesReason={
            "definitions": "this corpus names its terms by using them and states no definition"})
        code, out = run(["sweeps", self.fixture.map_path])
        self.assertEqual(code, NOT_VERIFIED, out)
        self.assertIn("reason declared:", out)

    def test_a_reason_a_live_cue_contradicts_fails(self):
        self.fixture.protocol(("definitions", "exceptions"), sweepCuesReason={
            "exceptions": "this corpus carves no exceptions"})
        code, out = run(["sweeps", self.fixture.map_path])
        self.assertEqual(code, 1, out)
        self.assertIn("stale claim", out)

    def test_a_sweep_with_nothing_to_examine_is_not_silent(self):
        """The rule is about a sweep that had candidates. A map whose walk accounted for every
        unit has nothing for a sweep to find, and that is the outcome, not a blind cue list."""
        self.fixture.write("mapping-inventory.json", {
            "inventoryVersion": 1, "corpus": "fixture",
            "rejected": [{"unit": f"p. 9 block {n}", "ground": "advice",
                          "note": "counsel on how to play; it obliges nothing"}
                         for n in (2, 3, 4)]})
        code, out = run(["sweeps", self.fixture.map_path])
        self.assertEqual(code, 0, out)
        self.assertIn("found nothing the map does not hold", out)


class TestExtentCoverageDelegatesToTheInventory(unittest.TestCase):
    def setUp(self):
        self.fixture = Fixture(required=("exceptions", "extent-coverage"))
        self.addCleanup(self.fixture.remove)

    def test_its_findings_are_the_inventorys_unaccounted_units(self):
        code, swept = run(["sweeps", self.fixture.map_path, "--list"])
        _, inventoried = run(["inventory", self.fixture.map_path, "--list"])
        self.assertEqual(code, NOT_VERIFIED, swept)
        self.assertIn("extent-coverage: 3 finding(s) in 4 candidate unit(s)", swept)
        self.assertIn("unaccounted: 3", inventoried)
        for block in ("p. 9 block 2", "p. 9 block 3", "p. 9 block 4"):
            self.assertIn(block, swept)

    def test_a_zero_yield_is_a_pass_and_not_a_silent_zero(self):
        self.fixture.protocol(("extent-coverage",))
        self.fixture.write("mapping-inventory.json", {
            "inventoryVersion": 1, "corpus": "fixture",
            "rejected": [{"unit": f"p. 9 block {n}", "ground": "advice",
                          "note": "counsel on how to play; it obliges nothing"}
                         for n in (2, 3, 4)]})
        code, out = run(["sweeps", self.fixture.map_path])
        self.assertEqual(code, 0, out)
        self.assertNotIn("X  extent-coverage", out)

    def test_it_reads_no_cues(self):
        self.fixture.protocol(("extent-coverage",), sweepCues={"extent-coverage": ["anything"]})
        code, out = run(["sweeps", self.fixture.map_path])
        self.assertEqual(code, 2, out)
        self.assertIn("delegates to `mapper inventory`", out)


class TestCrossReferencesDoNotCountASelfReference(unittest.TestCase):
    """0009 refuses a self-reference as a pointer. A section's own heading prints its own
    designation, so without this the sweep fires on every heading of a designated corpus and has
    sorted nothing."""

    def test_a_heading_naming_its_own_section_is_not_a_pointer(self):
        sweep = sweeps.REGISTRY["cross-references"]
        patterns = sweep.compiled([])
        own = corpus_unit("§ 107.25 heading", "heading",
                          "§ 107.25 Operation from a moving vehicle or aircraft.")
        other = corpus_unit("§ 107.25 ¶1", "paragraph",
                            "No person may operate as provided in § 107.29 of this chapter.")
        self.assertEqual(sweep.fired(own, patterns), [])
        self.assertTrue(sweep.fired(other, patterns))


def corpus_unit(key, kind, text):
    sys.path.insert(0, TOOLS)
    try:
        from mapper.corpus import Unit
    finally:
        sys.path.remove(TOOLS)
    return Unit(key, kind, text)


class TestTheProtocolHoldsItsCues(unittest.TestCase):
    def setUp(self):
        self.fixture = Fixture()
        self.addCleanup(self.fixture.remove)

    def test_cues_for_a_sweep_the_protocol_does_not_require_are_refused(self):
        self.fixture.protocol(("exceptions",), sweepCues={"tables": ["the following table"]})
        code, out = run(["protocol", self.fixture.map_path])
        self.assertEqual(code, 1, out)
        self.assertIn("does not require the 'tables' sweep", out)

    def test_a_cue_for_a_name_outside_the_closed_set_is_refused(self):
        self.fixture.protocol(("exceptions",), sweepCues={"omissions": ["anything"]})
        code, out = run(["protocol", self.fixture.map_path])
        self.assertEqual(code, 1, out)
        self.assertIn("outside the closed set of sweeps", out)

    def test_a_regex_that_does_not_compile_is_refused(self):
        self.fixture.protocol(("exceptions",), sweepCues={"exceptions": [{"regex": "("}]})
        code, out = run(["protocol", self.fixture.map_path])
        self.assertEqual(code, 1, out)
        self.assertIn("does not compile", out)

    def test_a_regex_matching_the_empty_string_is_refused(self):
        self.fixture.protocol(("exceptions",), sweepCues={"exceptions": [{"regex": "x*"}]})
        code, out = run(["protocol", self.fixture.map_path])
        self.assertEqual(code, 1, out)
        self.assertIn("matches the empty string", out)

    def test_a_reason_that_is_not_a_reason_is_refused(self):
        self.fixture.protocol(("exceptions",), sweepCuesReason={"exceptions": ""})
        code, out = run(["protocol", self.fixture.map_path])
        self.assertEqual(code, 1, out)
        self.assertIn("is not one", out)


class TestEveryCommittedMapIsSwept(unittest.TestCase):
    """The six maps, over three corpus grammars. A sweep nobody has run over a real corpus is one
    that has only ever seen this file's fixture."""

    def test_every_map_runs_every_sweep_it_requires(self):
        """A sweep with no candidates proves nothing -- unless the walk left no pile to sort.

        `0 candidate unit(s)` used to be enough to fail this test on its own, because no
        committed map accounted for every unit. Four of them now do (#267), and a sweep over a
        map with nothing unaccounted has nothing to examine by construction. So the guard is
        held to the maps that still have a pile: there, a sweep reporting no candidates is a
        sweep that stopped looking at the units it exists for.
        """
        paths = maps()
        self.assertTrue(paths, "no example maps -- this test proved nothing")
        for path in paths:
            with self.subTest(map=os.path.relpath(path, REPO)):
                code, out = run(["sweeps", path])
                self.assertIn(code, (0, NOT_VERIFIED), out)
                self.assertNotIn("NOT IMPLEMENTED", out)
                accounted = re.search(r"(\d+) of (\d+) unit\(s\) unaccounted", out)
                self.assertIsNotNone(accounted, out)
                if int(accounted.group(1)):
                    self.assertNotIn("in 0 candidate unit(s)", out)

    def test_every_sweep_in_the_closed_set_is_exercised_by_some_committed_map(self):
        """A sweep no map requires has only ever run on a fixture, and the closed set would be
        holding a name nothing in the repository reads."""
        required, read = set(), 0
        for path in maps():
            directory = os.path.dirname(path)
            # A map citing several corpora has one protocol per corpus (0040), named
            # `mapping-protocol-<sourceId>.json`; a map citing one has `mapping-protocol.json`.
            # Reading only the second name made this test open a file trial 10's map does not
            # have, and it would have gone on missing whatever sweeps such a map required.
            for name in sorted(os.listdir(directory)):
                if not (name.startswith("mapping-protocol") and name.endswith(".json")):
                    continue
                with open(os.path.join(directory, name), encoding="utf-8") as handle:
                    required.update(json.load(handle).get("requiredSweeps") or [])
                read += 1
        self.assertTrue(read, "no protocol was read -- this test proved nothing")
        self.assertEqual(required, set(protocol.SWEEPS))


if __name__ == "__main__":
    unittest.main()
