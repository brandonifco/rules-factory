#!/usr/bin/env python3
"""`factory trace` reports what an engine's records say about each entry, and labels how it knows (#576).

Every fixture is an engine `factory produce` wrote, so the trace reads the same records and the
same merge a real engine has. The two-corpus fixture (test_two_corpus_map.py) is small and cites two
corpora, which is what keeps them distinct is asserted on. The srd-52 composition is two published
maps of one corpus, which is what makes an entry id a derived fact rather than a recorded one.

Asserted:

  * every relationship is exactly one of recorded, derived, inferred, unknown; a recorded or derived
    one names its basis, an inferred one its mechanism, and an unknown one says why and is a gap;
  * named tests and mutations are the overlay's bytes, attributed to the overlay field that holds
    them, and a test with no mutation is unknown rather than assumed;
  * entry -> handler is derived through the generator's own model and contract (#582), required for
    an implemented entry and an optional hook otherwise, with the rule stated nowhere in trace.py;
  * entry -> implementation file is inferred from the handler declaration and never recorded, build
    output is not read, and an implemented entry nothing implements is unknown;
  * each corpus an entry cites is kept distinct, and a locator naming a corpus provenance does not
    record is unknown;
  * the topology is read from the record and from git and never corrected: standalone, embedded, a
    moved engine, no repository, and a record from before format 9;
  * the map's evidence quotations are never emitted and the engine's distribution always is, the
    same engine gives the same bytes, and no absolute path is printed;
  * a malformed overlay `tests` and an unreadable source file are gaps, not tracebacks;
  * what is not a produced engine is refused, exit 1, and a non-directory is a usage error, exit 2.

Run: python3 -m pytest tools/tests/factory/test_factory_trace.py
"""
import collections
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
REPO = os.path.dirname(TOOLS)
PACK = os.path.join(TOOLS, "pack-map.py")

sys.path.insert(0, TOOLS)
try:
    from factory import __main__ as factory
finally:
    sys.path.remove(TOOLS)

# The module, not its TestCase: a class bound here would be collected and run a second time.
from tests.factory import test_two_corpus_map as two  # noqa: E402

CLASSES = ("recorded", "derived", "inferred", "unknown")
HANDLER = """namespace TwoSection;

internal static partial class Handlers
{
    internal static partial Resolution<object> ListedInTheTable(Requests.ListedInTheTableRequest request) =>
        Resolution<object>.FromValue(true);
}
"""
MUTATION = ("Handlers.ListedInTheTable returned false (`FromValue(false)` for `FromValue(true)`); "
            "this test went red.")


def feed(directory, nupkgs):
    """A NuGet global packages folder holding `nupkgs`, laid out where intake looks for Id@Version."""
    for nupkg in nupkgs:
        # The id is every dot-separated part before the version, which is the last three numbers.
        parts = os.path.basename(nupkg)[:-len(".nupkg")].lower().split(".")
        package_id, version = ".".join(parts[:-3]), ".".join(parts[-3:])
        target = os.path.join(directory, package_id, version)
        os.makedirs(target, exist_ok=True)
        shutil.copy(nupkg, os.path.join(target, f"{package_id}.{version}.nupkg"))
    return directory


def run(argv, packages):
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.dict(os.environ, {"NUGET_PACKAGES": packages}), redirect_stdout(out), redirect_stderr(err):
        code = factory.main(argv)
    return code, out.getvalue(), err.getvalue()


def produce(nupkgs, corpora, name, out, *extra):
    argv = ["produce"]
    for nupkg in nupkgs:
        argv += ["--package", nupkg]
    for corpus in corpora:
        argv += ["--corpus", corpus]
    buffer = io.StringIO()
    with redirect_stdout(buffer), redirect_stderr(buffer):
        code = factory.main(argv + ["--name", name, "--out", out, "--allow-dirty", "--no-verify", *extra])
    assert code == factory.NOT_VERIFIED, buffer.getvalue()


def git_init(directory):
    subprocess.run(["git", "init", "-q", directory], check=True)


def facts(node):
    """Every relationship in the trace: each dict that carries an evidence class and a value."""
    if isinstance(node, dict):
        if "evidence" in node and "value" in node:
            yield node
            return
        for value in node.values():
            yield from facts(value)
    elif isinstance(node, list):
        for value in node:
            yield from facts(value)


def entry(trace, entry_id):
    (found,) = [e for e in trace["entries"] if e["id"]["value"] == entry_id]
    return found


class TraceOfATwoCorpusEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.mkdtemp(prefix="trace-")
        cls.map_dir = two.TwoCorpusMap.write_map(os.path.join(cls.shared, "two-section-fixture"))
        cls.nupkg = two.TwoCorpusMap.pack(cls.map_dir, os.path.join(cls.shared, "feed"))
        cls.packages = feed(os.path.join(cls.shared, "packages"), [cls.nupkg])
        cls.corpora = [os.path.join(cls.map_dir, name) for _, name, _ in two.SECTIONS]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.shared, True)

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="trace-case-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.engine = os.path.join(self.tmp, "engine")
        produce([self.nupkg], self.corpora, "TwoSection", self.engine)

    def trace(self, engine=None, packages=None):
        code, out, err = run(["trace", "--engine", engine or self.engine, "--json"], packages or self.packages)
        self.assertEqual(code, 0, err)
        return json.loads(out), out

    def overlay(self, entry_id, item):
        path = os.path.join(self.engine, "overlay", f"{entry_id}.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(item, handle, indent=2)

    def source(self, relative, text):
        path = os.path.join(self.engine, *relative.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)

    def record(self, change):
        path = os.path.join(self.engine, "provenance.json")
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
        change(document)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=2)

    def implemented(self, tests):
        self.overlay("listed-in-the-table", {"status": "implemented",
                                             "implementedIn": {"ruleset": "fixture", "version": 1}, "tests": tests})

    # --- the evidence classes -----------------------------------------------------------------

    def test_every_relationship_has_one_evidence_class_and_says_how_it_knows(self):
        self.implemented([{"test": "ListedTests.Holds", "mutation": MUTATION}, {"test": "ListedTests.Bare"}])
        self.source("src/TwoSection/Handlers/ListedInTheTable.cs", HANDLER)
        trace, _ = self.trace()
        seen = set()
        for fact in facts(trace):
            seen.add(fact["evidence"])
            self.assertIn(fact["evidence"], CLASSES, fact)
            if fact["evidence"] in ("recorded", "derived"):
                self.assertTrue(fact.get("basis"), fact)
            elif fact["evidence"] == "inferred":
                self.assertTrue(fact.get("mechanism"), fact)
            else:
                self.assertIsNone(fact["value"], fact)
                self.assertTrue(fact.get("why"), fact)
        self.assertEqual(seen, set(CLASSES))

    def test_every_unknown_is_also_a_gap_about_the_same_subject(self):
        self.implemented([{"test": "ListedTests.Bare"}])
        self.record(lambda r: r.pop("kernel"))
        trace, _ = self.trace()
        unknowns = collections.Counter()
        for listed in trace["entries"]:
            unknowns.update((f"entry:{listed['id']['value']}", f["why"]) for f in facts(listed)
                            if f["evidence"] == "unknown")
        for section in ("engine", "topology"):
            unknowns.update(("engine", f["why"]) for f in facts(trace[section]) if f["evidence"] == "unknown")
        self.assertEqual({why for _, why in unknowns} >= {"overlay/listed-in-the-table.json tests[0] records no "
                                                          "mutation the test was watched catching"}, True)
        gaps = collections.Counter((g["subject"], g["why"]) for g in trace["gaps"])
        self.assertEqual(unknowns - gaps, collections.Counter(), "an unknown with no gap of its own")
        self.assertEqual(sum(trace["summary"]["gaps"].values()), len(trace["gaps"]))

    # --- tests and mutations ------------------------------------------------------------------

    def test_named_tests_and_their_mutations_are_the_overlays_bytes_and_say_which_field(self):
        self.implemented([{"test": "ListedTests.Holds", "mutation": MUTATION}])
        listed = entry(self.trace()[0], "listed-in-the-table")
        (test,) = listed["tests"]
        self.assertEqual(test["name"], {"value": "ListedTests.Holds", "evidence": "recorded",
                                        "basis": "overlay/listed-in-the-table.json tests[0].test"})
        self.assertEqual(test["mutation"], {"value": MUTATION, "evidence": "recorded",
                                            "basis": "overlay/listed-in-the-table.json tests[0].mutation"})
        self.assertEqual(listed["status"]["basis"], "overlay/listed-in-the-table.json status")
        self.assertEqual(listed["package"]["basis"], "provenance.json maps[0].packageId, the one map package, "
                                                     "whose map/corpus-map.json holds the entry")
        self.assertEqual(listed["implementedIn"]["value"], {"ruleset": "fixture", "version": 1})

    def test_a_test_with_no_mutation_is_unknown_and_a_gap(self):
        self.implemented([{"test": "ListedTests.Bare"}])
        trace, _ = self.trace()
        (test,) = entry(trace, "listed-in-the-table")["tests"]
        self.assertEqual(test["mutation"]["evidence"], "unknown")
        self.assertIn({"subject": "entry:listed-in-the-table", "relationship": "test -> mutation",
                       "why": test["mutation"]["why"]}, trace["gaps"])

    def test_an_implemented_entry_that_names_no_test_is_a_gap(self):
        self.implemented([])
        trace, _ = self.trace()
        self.assertIn({"subject": "entry:listed-in-the-table", "relationship": "entry -> test",
                       "why": "the entry is implemented and names no test"}, trace["gaps"])

    def test_an_entry_with_no_overlay_file_takes_its_status_from_the_map_and_says_so(self):
        water = entry(self.trace()[0], "w-is-water-only")
        self.assertEqual(water["status"]["value"], "mapped")
        self.assertIn("map/corpus-map.json", water["status"]["basis"])
        self.assertIn("no overlay/w-is-water-only.json", water["status"]["basis"])
        self.assertNotIn("implementedIn", water)

    def test_tests_that_are_not_a_list_are_a_gap_not_a_traceback(self):
        self.implemented(5)
        trace, _ = self.trace()
        listed = entry(trace, "listed-in-the-table")
        self.assertEqual(listed["tests"], [])
        self.assertEqual([g["why"] for g in trace["gaps"] if g["relationship"] == "entry -> test"],
                         ["overlay/listed-in-the-table.json tests is not a list, so it names no test anybody can run"])

    # --- implementation -----------------------------------------------------------------------

    def test_implementation_is_inferred_from_the_handler_and_never_recorded(self):
        self.implemented([{"test": "ListedTests.Holds", "mutation": MUTATION}])
        self.source("src/TwoSection/Handlers/ListedInTheTable.cs", HANDLER)
        self.source("src/TwoSection/Rules/Table.cs",
                    "namespace TwoSection;\n\ninternal static class Table\n{\n"
                    "    internal const string Entry = \"listed-in-the-table\";\n}\n")
        # Build output names the entry too, and is not the engine's code.
        self.source("src/TwoSection/obj/Debug/Stale.cs", HANDLER)
        trace, _ = self.trace()
        candidates = entry(trace, "listed-in-the-table")["implementation"]
        self.assertEqual([c["value"] for c in candidates],
                         [{"path": "src/TwoSection/Handlers/ListedInTheTable.cs", "symbol": "Handlers.ListedInTheTable"},
                          {"path": "src/TwoSection/Rules/Table.cs", "symbol": None}])
        self.assertEqual({c["evidence"] for c in candidates}, {"inferred"})
        self.assertIn("reviewscope.partial_members", candidates[0]["mechanism"])
        self.assertIn("reviewscope.entry_references", candidates[1]["mechanism"])
        for listed in trace["entries"]:
            for fact in listed["implementation"]:
                self.assertIn(fact["evidence"], ("inferred", "unknown"))

    def test_a_member_of_another_partial_type_is_not_a_handler(self):
        self.implemented([{"test": "ListedTests.Holds", "mutation": MUTATION}])
        self.source("src/TwoSection/Mixed.cs",
                    "namespace TwoSection;\n\ninternal static partial class Handlers\n{\n}\n\n"
                    "internal static partial class Other\n{\n    internal static void ListedInTheTable() { }\n}\n")
        (candidate,) = entry(self.trace()[0], "listed-in-the-table")["implementation"]
        self.assertEqual(candidate["value"], {"path": "src/TwoSection/Mixed.cs", "symbol": None})
        self.assertIn("reviewscope.entry_references", candidate["mechanism"])

    def test_a_handler_file_that_also_extends_the_request_type_still_names_the_handler(self):
        """srd-52-combat's shape: the handler file declares the entry's inputs on its partial request
        type (#93) beside the partial Handlers, and the handler is still the one it writes."""
        self.implemented([{"test": "ListedTests.Holds", "mutation": MUTATION}])
        self.source("src/TwoSection/Handlers/ListedInTheTable.cs",
                    "namespace TwoSection;\n\nnamespace Requests\n{\n    public sealed partial class "
                    "ListedInTheTableRequest\n    {\n        public int Material { get; init; }\n    }\n}\n\n"
                    + HANDLER.split("\n", 2)[2])
        candidates = entry(self.trace()[0], "listed-in-the-table")["implementation"]
        self.assertEqual(candidates[0]["value"], {"path": "src/TwoSection/Handlers/ListedInTheTable.cs",
                                                  "symbol": "Handlers.ListedInTheTable"})

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root reads a file whatever its mode")
    def test_a_source_file_that_cannot_be_read_is_a_gap_not_a_traceback(self):
        self.source("src/TwoSection/Handlers/ListedInTheTable.cs", HANDLER)
        path = os.path.join(self.engine, "src", "TwoSection", "Handlers", "ListedInTheTable.cs")
        os.chmod(path, 0)
        self.addCleanup(os.chmod, path, 0o644)
        trace, _ = self.trace()
        (gap,) = [g for g in trace["gaps"] if g["relationship"] == "engine -> implementation files"]
        self.assertIn("src/TwoSection/Handlers/ListedInTheTable.cs could not be read", gap["why"])

    def test_an_implemented_entrys_handler_is_derived_from_the_generator_and_required(self):
        self.implemented([{"test": "ListedTests.Holds", "mutation": MUTATION}])
        handler = entry(self.trace()[0], "listed-in-the-table")["handler"]
        self.assertEqual(handler["value"], {"symbol": "Handlers.ListedInTheTable", "required": True})
        self.assertEqual(handler["evidence"], "derived")
        self.assertIn("contracts.handler over semantics.Model", handler["basis"])

    def test_an_entry_that_is_not_implemented_has_an_optional_hook(self):
        handler = entry(self.trace()[0], "w-is-water-only")["handler"]
        self.assertEqual(handler["value"], {"symbol": "Handlers.WIsWaterOnly", "required": False})

    def test_whether_a_handler_is_required_is_the_generators_rule_and_not_restated(self):
        self.implemented([{"test": "ListedTests.Holds", "mutation": MUTATION}])
        real = factory.trace_step.semantics.contract
        with mock.patch.object(factory.trace_step.semantics, "contract",
                               side_effect=lambda model, item: dict(real(model, item), required=False)):
            handler = entry(self.trace()[0], "listed-in-the-table")["handler"]
        self.assertFalse(handler["value"]["required"])

    def test_the_handler_class_is_the_descriptors_and_the_trace_follows_it(self):
        """#599: the class the trace reports and searches for is contracts.py's, not its own."""
        self.implemented([{"test": "ListedTests.Holds", "mutation": MUTATION}])
        self.source("src/TwoSection/Handlers/ListedInTheTable.cs", HANDLER.replace("Handlers", "Hooks"))
        contracts = factory.trace_step.contracts
        today = entry(self.trace()[0], "listed-in-the-table")["implementation"]
        self.assertEqual([c["value"]["symbol"] for c in today], [None],
                         "under the generator's class today the file only names the entry; it is not a handler")
        with mock.patch.object(contracts, "HANDLER_CLASS", "Hooks"):
            listed = entry(self.trace()[0], "listed-in-the-table")
        self.assertEqual(listed["handler"]["value"], {"symbol": "Hooks.ListedInTheTable", "required": True})
        self.assertEqual(listed["implementation"][0]["value"],
                         {"path": "src/TwoSection/Handlers/ListedInTheTable.cs", "symbol": "Hooks.ListedInTheTable"})
        self.assertIn("declares the partial Hooks", listed["implementation"][0]["mechanism"])

    def test_the_signature_forms_are_the_descriptors_and_the_trace_follows_them(self):
        """#599: a changed signature form changes which hand-written file the trace recognises."""
        self.implemented([{"test": "ListedTests.Holds", "mutation": MUTATION}])
        self.source("src/TwoSection/Handlers/ListedInTheTable.cs", HANDLER.replace("Resolution<object>", "Outcome<object>"))
        contracts = factory.trace_step.contracts

        def declaring():
            return [c["value"]["path"] for c in entry(self.trace()[0], "listed-in-the-table")["implementation"]
                    if c["value"] and c["value"].get("symbol")]
        self.assertEqual(declaring(), [])
        with mock.patch.dict(contracts.HANDLER_RETURNS, {"required": "Outcome<{output}>"}):
            self.assertEqual(declaring(), ["src/TwoSection/Handlers/ListedInTheTable.cs"])
            mechanism = entry(self.trace()[0], "listed-in-the-table")["implementation"][0]["mechanism"]
        self.assertIn("`partial Outcome<...> <Member>(`", mechanism)

    def test_a_map_the_generator_cannot_model_leaves_every_handler_unknown_and_traces_the_rest(self):
        with mock.patch.object(factory.trace_step.semantics, "Model",
                               side_effect=factory.trace_step.semantics.GenerationError("two entries, one member")):
            trace, _ = self.trace()
        for listed in trace["entries"]:
            self.assertEqual(listed["handler"]["evidence"], "unknown")
            self.assertIn("two entries, one member", listed["handler"]["why"])
            self.assertEqual(listed["locator"]["evidence"], "recorded")
        self.assertEqual(trace["summary"]["gaps"]["entry -> handler"], 2)

    def test_the_handler_basis_says_it_was_not_read_from_the_generated_file(self):
        basis = entry(self.trace()[0], "w-is-water-only")["handler"]["basis"]
        self.assertIn("not read from Generated/Contracts.g.cs", basis)

    def test_an_implemented_entry_nothing_implements_is_unknown_and_a_gap(self):
        self.implemented([{"test": "ListedTests.Holds", "mutation": MUTATION}])
        trace, _ = self.trace()
        (fact,) = entry(trace, "listed-in-the-table")["implementation"]
        self.assertEqual(fact["evidence"], "unknown")
        self.assertIn({"subject": "entry:listed-in-the-table", "relationship": "entry -> implementation",
                       "why": fact["why"]}, trace["gaps"])

    # --- corpora and locators -----------------------------------------------------------------

    def test_each_corpus_an_entry_cites_is_kept_distinct(self):
        trace, _ = self.trace()
        self.assertEqual([c["sourceId"]["value"] for c in trace["corpora"]], ["cfr-9-9.101", "cfr-9-9.102"])
        (package,) = trace["maps"]
        self.assertEqual(package["corpora"]["value"], ["cfr-9-9.101", "cfr-9-9.102"])
        self.assertEqual(package["principalCorpus"]["value"], "cfr-9-9.101")
        for entry_id, source in (("listed-in-the-table", "cfr-9-9.101"), ("w-is-water-only", "cfr-9-9.102")):
            listed = entry(trace, entry_id)
            self.assertEqual(listed["locator"]["value"]["sourceId"], source)
            self.assertEqual(listed["corpus"], {"value": source, "evidence": "derived",
                                                "basis": "the locator's sourceId is a sourceId provenance.json "
                                                         "corpora[] records"})
            self.assertEqual(listed["segment"]["evidence"], "unknown")

    def test_a_locator_naming_a_corpus_provenance_does_not_record_is_unknown(self):
        self.record(lambda r: r.update(corpora=[c for c in r["corpora"] if c["sourceId"] != "cfr-9-9.102"]))
        trace, _ = self.trace()
        water = entry(trace, "w-is-water-only")
        self.assertEqual(water["corpus"]["evidence"], "unknown")
        self.assertIn("cfr-9-9.102", water["corpus"]["why"])
        self.assertIn({"subject": "entry:w-is-water-only", "relationship": "locator -> corpus",
                       "why": water["corpus"]["why"]}, trace["gaps"])

    def test_the_maps_evidence_is_never_emitted_and_the_distribution_always_is(self):
        trace, text = self.trace()
        self.assertEqual(trace["engine"]["distribution"], {"value": "public", "evidence": "recorded",
                                                           "basis": "provenance.json distribution"})
        for row in two.ENTRIES:
            self.assertNotIn(row["evidence"], text)
        for _, _, corpus in two.SECTIONS:
            for line in corpus.splitlines():
                if "(a)" in line or "(b)" in line:
                    self.assertNotIn(line.split(")", 1)[1].split("<")[0].strip(), text)

    def test_the_same_engine_gives_the_same_bytes_and_no_absolute_path(self):
        _, first = self.trace()
        _, second = self.trace()
        self.assertEqual(first, second)
        self.assertNotIn(self.tmp, first)
        self.assertNotIn(os.path.realpath(self.tmp), first)

    # --- topology -----------------------------------------------------------------------------

    def test_a_standalone_engine_agrees_with_its_record(self):
        git_init(self.engine)
        topology = self.trace()[0]["topology"]
        self.assertEqual(topology["recordedEnginePath"]["value"], None)
        self.assertEqual(topology["recordedEnginePath"]["evidence"], "recorded")
        self.assertEqual(topology["observedEnginePath"]["value"], None)
        self.assertTrue(topology["agrees"])

    def test_an_engine_in_no_repository_is_unknown_and_not_assumed(self):
        trace, _ = self.trace()
        topology = trace["topology"]
        self.assertEqual(topology["observedEnginePath"]["evidence"], "unknown")
        self.assertIsNone(topology["agrees"])
        self.assertIn("engine -> repository root", [g["relationship"] for g in trace["gaps"]])

    def test_an_embedded_engine_is_traced_from_the_path_its_record_names(self):
        host = os.path.join(self.tmp, "host")
        git_init(host)
        produce([self.nupkg], self.corpora, "TwoSection", os.path.join(host, "engine"), "--repo-root", host)
        topology = self.trace(os.path.join(host, "engine"))[0]["topology"]
        self.assertEqual(topology["recordedEnginePath"]["value"], "engine")
        self.assertEqual(topology["observedEnginePath"]["value"], "engine")
        self.assertTrue(topology["agrees"])

    def test_a_moved_engine_is_reported_and_not_corrected(self):
        host = os.path.join(self.tmp, "host")
        git_init(host)
        produce([self.nupkg], self.corpora, "TwoSection", os.path.join(host, "engine"), "--repo-root", host)
        os.makedirs(os.path.join(host, "elsewhere"))
        os.rename(os.path.join(host, "engine"), os.path.join(host, "elsewhere", "engine"))
        trace, _ = self.trace(os.path.join(host, "elsewhere", "engine"))
        topology = trace["topology"]
        self.assertEqual(topology["recordedEnginePath"]["value"], "engine")
        self.assertEqual(topology["observedEnginePath"]["value"], "elsewhere/engine")
        self.assertFalse(topology["agrees"])
        (gap,) = [g for g in trace["gaps"] if g["relationship"] == "engine -> repository root"]
        self.assertIn("'engine'", gap["why"])
        self.assertIn("'elsewhere/engine'", gap["why"])

    def test_a_record_before_format_9_is_read_as_a_repository_root_and_says_it_was_derived(self):
        self.record(lambda r: r.pop("repository"))
        said = self.trace()[0]["topology"]["recordedEnginePath"]
        self.assertEqual(said["value"], None)
        self.assertEqual(said["evidence"], "derived")
        self.assertIn("repository.from_record", said["basis"])

    def test_a_repository_section_with_no_engine_path_is_unknown_not_null(self):
        git_init(self.engine)
        self.record(lambda r: r["repository"].pop("enginePath"))
        trace, _ = self.trace()
        topology = trace["topology"]
        self.assertEqual(topology["recordedEnginePath"]["evidence"], "unknown")
        self.assertIsNone(topology["agrees"])
        self.assertIn("engine -> recorded enginePath", [g["relationship"] for g in trace["gaps"]])

    def test_a_map_fact_the_record_does_not_carry_is_unknown(self):
        self.record(lambda r: r["maps"][0].pop("nupkgSha256"))
        trace, _ = self.trace()
        self.assertEqual(trace["maps"][0]["nupkgSha256"]["evidence"], "unknown")
        self.assertIn("map:RulesFactory.Maps.TwoSectionFixture -> nupkgSha256",
                      [g["relationship"] for g in trace["gaps"]])

    def test_a_fact_an_older_record_does_not_carry_is_unknown(self):
        self.record(lambda r: r.pop("kernel"))
        trace, _ = self.trace()
        self.assertEqual(trace["engine"]["kernel"]["version"]["evidence"], "unknown")
        self.assertIn("engine -> kernel.version", [g["relationship"] for g in trace["gaps"]])

    # --- refusals -----------------------------------------------------------------------------

    def test_a_directory_with_no_record_is_refused(self):
        code, out, err = run(["trace", "--engine", self.tmp, "--json"], self.packages)
        self.assertEqual((code, out), (1, ""))
        self.assertIn("has no provenance.json", err)

    def test_a_record_that_is_not_json_is_refused(self):
        with open(os.path.join(self.engine, "provenance.json"), "w", encoding="utf-8") as handle:
            handle.write("{")
        code, out, err = run(["trace", "--engine", self.engine, "--json"], self.packages)
        self.assertEqual((code, out), (1, ""))
        self.assertIn("cannot read provenance.json", err)

    def test_a_package_that_is_not_here_is_refused(self):
        code, out, err = run(["trace", "--engine", self.engine, "--json"], os.path.join(self.tmp, "empty"))
        self.assertEqual((code, out), (1, ""))
        self.assertIn("the entries cannot be traced", err)

    def test_an_overlay_that_does_not_merge_is_refused(self):
        self.overlay("no-such-entry", {"status": "implemented"})
        code, out, err = run(["trace", "--engine", self.engine, "--json"], self.packages)
        self.assertEqual((code, out), (1, ""))
        self.assertIn("do not merge", err)

    def test_an_engine_that_is_not_a_directory_is_a_usage_error(self):
        code, _, err = run(["trace", "--engine", os.path.join(self.tmp, "absent"), "--json"], self.packages)
        self.assertEqual(code, 2, err)


class TraceOfAComposedEngine(unittest.TestCase):
    """Two published maps of one corpus (0067): an entry id is the factory's composition of it."""

    COMPOSED = ("srd-52-combat", "srd-52-conditions")

    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.mkdtemp(prefix="trace-composed-")
        out = os.path.join(cls.shared, "feed")
        for slug in cls.COMPOSED:
            subprocess.run([sys.executable, PACK, os.path.join(REPO, "examples", slug), "--out", out], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        nupkgs = sorted(os.path.join(out, n) for n in os.listdir(out) if n.endswith(".nupkg"))
        cls.packages = feed(os.path.join(cls.shared, "packages"), nupkgs)
        cls.engine = os.path.join(cls.shared, "engine")
        produce(nupkgs, [os.path.join(REPO, "examples", "srd-52-combat", "srd-5.2.1.txt")], "Srd52", cls.engine)
        code, out, err = run(["trace", "--engine", cls.engine, "--json"], cls.packages)
        assert code == 0, err
        cls.trace = json.loads(out)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.shared, True)

    def test_both_packages_are_traced_and_each_entry_names_the_one_it_came_from(self):
        self.assertEqual([m["packageId"]["value"] for m in self.trace["maps"]],
                         ["RulesFactory.Maps.Srd52Combat", "RulesFactory.Maps.Srd52Conditions"])
        prone = entry(self.trace, "Srd52Conditions.prone")
        self.assertEqual(prone["package"]["value"], "RulesFactory.Maps.Srd52Conditions")
        self.assertEqual(prone["package"]["evidence"], "derived")
        self.assertEqual(prone["id"]["evidence"], "derived")
        self.assertIn("compose.union", prone["id"]["basis"])
        self.assertIn("entries['prone']", prone["name"]["basis"], "the basis names the id the package's map holds")
        for listed in self.trace["entries"]:
            self.assertEqual(listed["id"]["evidence"], "derived")
            self.assertTrue(listed["id"]["value"].startswith(("Srd52Combat.", "Srd52Conditions.")))


if __name__ == "__main__":
    unittest.main()
