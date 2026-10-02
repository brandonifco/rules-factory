#!/usr/bin/env python3
"""What kind of review a diff owes, computed (decision 0076, #595).

`tools/factory/reviewclass.py` is the one reading `pr-policy.py`, `conformance-gate.py` and
`review-packet.py` share, so it is tested here as what it is: a function of the changed paths and
the bytes on each side of them. The rails' own tests (test_factory_rails.py) hold the same five
classes to the tools that act on them.

The five classes each have a case that proves it, and each protection has a case that proves the
class does not **fall** to it: the diff decides and the pull request's words only add review, so a
claim cannot lower a class, an exemption must be claimed, and anything not proved inert is an
implementation. A test here is written with the mutation that makes it fail named beside it.

Run: python3 -m pytest -p no:cacheprovider tools/tests/factory/test_review_class.py
"""
import hashlib
import json
import os
import sys
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "factory"))

import ownership  # noqa: E402
import reviewclass as rc  # noqa: E402

NAME = "Reykholt"
PATTERNS = ["src/**", "tests/**", "overlay/**", "RulesFactory.Packages.g.props", "corpus/**", "docs/decisions/**"]


def FCLASS(path):  # noqa: N802  (resolved through `rc` at call time, so a mutant module is the one asked)
    return rc.factory_class(ownership, NAME)(path)


RECORD = "docs/decisions/0007-owner-rulings.md"
GENERATED = f"src/{NAME}/Generated/MapEntries.g.cs"
PROPS = "RulesFactory.Packages.g.props"
HANDLER = f"src/{NAME}/Handlers.Core.cs"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def record(maps=(("Pkg", "1.0.0", "aa"),), corpora=(("src1", "cc"),), kernel="0.3.0", factory="1.1.0",
           dirty=False, generated=None, randomness="none"):
    return {"factory": {"version": factory, "dirty": dirty}, "kernel": {"version": kernel},
            "maps": [{"packageId": p, "version": v, "nupkgSha256": d} for p, v, d in maps],
            "corpora": [{"sourceId": s, "contentHash": h} for s, h in corpora],
            "randomness": randomness,
            "generated": [{"path": p, "sha256": h} for p, h in (generated or {}).items()], "managed": []}


class Repo:
    """A base and a head, as bytes, handed to the classifier the way a rail would read them."""

    def __init__(self, base=None, head=None):
        self.base, self.head = dict(base or {}), dict(head or {})

    def read(self, path, side):
        return (self.base if side == "base" else self.head).get(path)

    def classify(self, changed, patterns=PATTERNS):
        return rc.classify(changed, patterns, read=self.read, fclass=FCLASS)


def doc(text):
    return text.encode("utf-8")


class TestEachClass(unittest.TestCase):
    """The five classes, each from a diff that is exactly that and nothing else."""

    def test_a_handler_is_a_semantic_implementation(self):
        # mutation: classify a hand-written .cs under src/ as documentation
        repo = Repo({HANDLER: b"int F() { return 1; }"}, {HANDLER: b"int F() { return 2; }"})
        result = repo.classify({HANDLER: "MODIFIED"})
        self.assertEqual(result["class"], rc.SEMANTIC_IMPLEMENTATION)
        self.assertEqual(result["semanticFiles"], [HANDLER])
        effective, problems, _ = rc.judge(result, None)
        self.assertEqual(effective, rc.SEMANTIC_IMPLEMENTATION)
        self.assertEqual(rc.owes(effective), {"entries": True, "self_review": True, "ruling_review": False,
                                              "packet": True, "verdict": True})

    def test_an_overlay_row_is_a_semantic_implementation(self):
        # mutation: let overlay/** fall to documentation because its extension is .json
        result = Repo().classify({"overlay/altitude-limit.json": "ADDED"})
        self.assertEqual(result["class"], rc.SEMANTIC_IMPLEMENTATION)

    def test_the_corpus_is_never_derived_though_the_table_calls_it_generated(self):
        # mutation: let `corpus/*` (a GENERATED row) count as a file the factory writes
        self.assertEqual(FCLASS("corpus/book.txt"), "generated")
        result = Repo().classify({"corpus/book.txt": "MODIFIED", "provenance.json": "MODIFIED"})
        self.assertEqual(result["class"], rc.SEMANTIC_IMPLEMENTATION)

    def test_a_new_decision_record_that_overrules_nothing_is_decision_record_only(self):
        # mutation: classify a decision record as an implementation because it is on the surface
        repo = Repo({}, {RECORD: doc("# 0007\n\n- **Status:** accepted\n- **Relates to:** 0001 to 0006\n")})
        result = repo.classify({RECORD: "ADDED"})
        self.assertEqual(result["class"], rc.DECISION_RECORD_ONLY)
        self.assertEqual(result["semanticFiles"], [])
        effective, problems, hints = rc.judge(result, rc.DECISION_RECORD_ONLY)
        self.assertEqual((effective, problems, hints), (rc.DECISION_RECORD_ONLY, [], []))
        self.assertEqual(rc.owes(effective), {"entries": False, "self_review": False, "ruling_review": False,
                                              "packet": False, "verdict": False})

    def test_prose_about_being_overruled_is_not_a_supersession(self):
        # The real Reykholt record 0007 says it is "the owner's to overrule, by a later record" and
        # "Overturned only by a later decision record". mutation: match those words anywhere in the
        # text rather than as a header line, and a record that merely says how it can be changed is a ruling.
        text = ("# 0007\n\n- **Status:** accepted\n- **Decided by:** the owner. They are the owner's to overrule, "
                "by a later record and never by editing this one.\n\n- Overturned only by a later decision "
                "record, never by editing this one.\n")
        result = Repo({}, {RECORD: doc(text)}).classify({RECORD: "ADDED"})
        self.assertEqual(result["class"], rc.DECISION_RECORD_ONLY)

    def test_a_record_that_supersedes_another_is_a_semantic_ruling(self):
        # mutation: drop the SUPERSESSION header check, and a ruling already in force changes unreviewed
        for header in ("- **Supersedes:** 0003", "**Supersedes**: decision 0003", "Overrules: 0003"):
            with self.subTest(header=header):
                result = Repo({}, {RECORD: doc(f"# 0008\n\n{header}\n")}).classify({RECORD: "ADDED"})
                self.assertEqual(result["class"], rc.SEMANTIC_RULING)
                self.assertEqual(result["semanticFiles"], [RECORD])
                self.assertEqual(result["decisionRecords"], [RECORD])

    def test_an_existing_decision_record_edited_is_a_semantic_ruling(self):
        # mutation: treat any edit to a record as cosmetic
        repo = Repo({RECORD: doc("1. The furthest player wins.\n")}, {RECORD: doc("1. The nearest player wins.\n")})
        result = repo.classify({RECORD: "MODIFIED"})
        self.assertEqual(result["class"], rc.SEMANTIC_RULING)
        self.assertEqual(rc.owes(rc.SEMANTIC_RULING), {"entries": False, "self_review": False, "ruling_review": True,
                                                       "packet": True, "verdict": True})

    def test_a_whitespace_only_edit_of_a_record_is_cosmetic(self):
        # mutation: compare the bytes and not the words, and a reflow is a ruling
        repo = Repo({RECORD: doc("The furthest\nplayer wins.\n")}, {RECORD: doc("The furthest player   wins.\n\n")})
        self.assertEqual(repo.classify({RECORD: "MODIFIED"})["class"], rc.DECISION_RECORD_ONLY)

    def test_a_deleted_record_is_a_semantic_ruling(self):
        # mutation: let a deletion pass as an edit with no text to compare
        repo = Repo({RECORD: doc("1. The furthest player wins.\n")}, {})
        self.assertEqual(repo.classify({RECORD: "DELETED"})["class"], rc.SEMANTIC_RULING)

    def test_a_record_that_cannot_be_read_is_a_semantic_ruling(self):
        # mutation: let an unreadable head fall through as an addition that overrules nothing
        repo = Repo({}, {RECORD: b"\xff\xfe not utf-8"})
        self.assertEqual(repo.classify({RECORD: "ADDED"})["class"], rc.SEMANTIC_RULING)

    def test_the_index_beside_the_records_is_documentation(self):
        result = Repo().classify({"docs/decisions/README.md": "MODIFIED"})
        self.assertEqual(result["class"], rc.DOCUMENTATION)

    def test_a_readme_is_documentation_off_the_surface(self):
        result = Repo().classify({"README.md": "MODIFIED"})
        self.assertEqual((result["class"], result["onSurface"]), (rc.DOCUMENTATION, []))
        self.assertEqual(rc.judge(result, None), (rc.DOCUMENTATION, [], []))

    def test_a_markdown_file_inside_a_semantic_directory_is_not_proved_inert(self):
        # A file under src/ or tests/ can be an embedded resource or a fixture a test parses, and nothing
        # here can tell. mutation: call every .md documentation wherever it sits
        for path in (f"src/{NAME}/README.md", f"tests/{NAME}.Tests/cases.md"):
            with self.subTest(path=path):
                self.assertEqual(Repo().classify({path: "MODIFIED"})["class"], rc.SEMANTIC_IMPLEMENTATION)

    def test_a_comment_only_change_to_a_handler_is_documentation(self):
        # mutation: return True from comment_only whenever the file changed
        repo = Repo({HANDLER: b"int F() { return 1; } // the old note\n"},
                    {HANDLER: b"int F() { return 1; } // a better note\n/* and a block */\n"})
        result = repo.classify({HANDLER: "MODIFIED"})
        self.assertEqual(result["class"], rc.DOCUMENTATION)
        self.assertEqual(rc.judge(result, rc.DOCUMENTATION)[0], rc.DOCUMENTATION)

    def test_a_factory_update_with_the_rules_unmoved_is_generated_or_provenance(self):
        # mutation: let any change confined to factory-written files through, whatever the record says
        repo = FactoryUpdate().repo()
        result = repo.classify(FactoryUpdate.paths())
        self.assertEqual(result["class"], rc.GENERATED_OR_PROVENANCE)
        self.assertTrue(result["regeneration"])
        self.assertTrue(result["onSurface"], "it touches the surface, which is why it must be claimed")
        self.assertEqual(rc.judge(result, rc.GENERATED_OR_PROVENANCE)[0], rc.GENERATED_OR_PROVENANCE)
        self.assertEqual(result["semanticFiles"], [])


class TestAnExemptionMustBeClaimed(unittest.TestCase):
    """The diff decides; the pull request's words can only add review."""

    def decision_only(self):
        return Repo({}, {RECORD: doc("# 0007\n")}).classify({RECORD: "ADDED"})

    def test_an_unclaimed_exemption_is_reviewed_as_an_implementation_and_says_how_to_claim_it(self):
        # mutation: return the computed non-semantic class when nothing is declared
        effective, problems, hints = rc.judge(self.decision_only(), None)
        self.assertEqual(effective, rc.SEMANTIC_IMPLEMENTATION)
        self.assertEqual(problems, [], "an unclaimed exemption is not a finding; it is the old behaviour")
        self.assertIn("review class: decision-record-only", hints[0])

    def test_a_claim_cannot_lower_what_the_diff_computes(self):
        # mutation: let a declared non-semantic class win over a computed semantic one
        repo = Repo({HANDLER: b"int F() { return 1; }"}, {HANDLER: b"int F() { return 2; }"})
        result = repo.classify({HANDLER: "MODIFIED"})
        for claimed in (rc.DECISION_RECORD_ONLY, rc.GENERATED_OR_PROVENANCE, rc.DOCUMENTATION, rc.SEMANTIC_RULING):
            with self.subTest(claimed=claimed):
                effective, problems, _ = rc.judge(result, claimed)
                self.assertEqual(effective, rc.SEMANTIC_IMPLEMENTATION)
                self.assertTrue(problems, "a claim the diff contradicts is a finding")

    def test_a_ruling_diff_claimed_as_a_record_is_still_a_ruling(self):
        # mutation: honour decision-record-only for an edited record
        repo = Repo({RECORD: doc("1. A.\n")}, {RECORD: doc("1. B.\n")})
        effective, problems, _ = rc.judge(repo.classify({RECORD: "MODIFIED"}), rc.DECISION_RECORD_ONLY)
        self.assertEqual(effective, rc.SEMANTIC_RULING)
        self.assertTrue(problems)

    def test_an_unclaimed_exemption_hands_the_reviewer_the_files_the_diff_computed_inert(self):
        # mutation: hand the reviewer result["semanticFiles"], which follows the computed class and is empty here
        result = self.decision_only()
        effective, _, _ = rc.judge(result, None)
        self.assertEqual(result["semanticFiles"], [])
        self.assertEqual(rc.semantic_files(result, effective), [RECORD])
        self.assertEqual(rc.semantic_files(result, rc.DECISION_RECORD_ONLY), [])

    def test_a_claim_may_raise_a_class(self):
        # A new record claimed as a ruling is reviewed as one; a ruling claimed as an implementation is too.
        effective, problems, _ = rc.judge(self.decision_only(), rc.SEMANTIC_RULING)
        self.assertEqual((effective, problems), (rc.SEMANTIC_RULING, []))
        effective, _, _ = rc.judge(self.decision_only(), rc.SEMANTIC_IMPLEMENTATION)
        self.assertEqual(effective, rc.SEMANTIC_IMPLEMENTATION)
        edited = Repo({RECORD: doc("A.")}, {RECORD: doc("B.")}).classify({RECORD: "MODIFIED"})
        self.assertEqual(rc.judge(edited, rc.SEMANTIC_IMPLEMENTATION)[0], rc.SEMANTIC_IMPLEMENTATION)

    def test_a_claim_of_the_wrong_exemption_is_a_finding_and_a_review(self):
        # mutation: accept any non-semantic claim for any non-semantic diff
        effective, problems, _ = rc.judge(self.decision_only(), rc.GENERATED_OR_PROVENANCE)
        self.assertEqual(effective, rc.SEMANTIC_IMPLEMENTATION)
        self.assertTrue(problems)

    def test_an_unknown_class_is_a_finding_and_claims_nothing(self):
        effective, problems, hints = rc.judge(self.decision_only(), "docs-only")
        self.assertEqual(effective, rc.SEMANTIC_IMPLEMENTATION)
        self.assertIn("is not a class", problems[0])

    def test_nothing_on_the_surface_needs_no_claim(self):
        result = Repo().classify({"README.md": "MODIFIED"})
        self.assertEqual(rc.judge(result, None), (rc.DOCUMENTATION, [], []))


class TestItFailsClosed(unittest.TestCase):
    """Anything not shown inert is an implementation."""

    def test_a_ruling_beside_a_handler_is_an_implementation(self):
        # mutation: let the weaker class win in an aggregate
        repo = Repo({HANDLER: b"int F() { return 1; }", RECORD: doc("A.")},
                    {HANDLER: b"int F() { return 2; }", RECORD: doc("B.")})
        result = repo.classify({HANDLER: "MODIFIED", RECORD: "MODIFIED"})
        self.assertEqual(result["class"], rc.SEMANTIC_IMPLEMENTATION)

    def test_a_decision_record_with_a_handler_is_an_implementation(self):
        repo = Repo({HANDLER: b"int F() { return 1; }"}, {HANDLER: b"int F() { return 2; }", RECORD: doc("# 0007\n")})
        result = repo.classify({HANDLER: "MODIFIED", RECORD: "ADDED"})
        self.assertEqual(result["class"], rc.SEMANTIC_IMPLEMENTATION)

    def test_a_path_the_classifier_cannot_read_is_an_implementation(self):
        # mutation: swallow the exception and call the path documentation
        def broken(path, side):
            raise RuntimeError("the API is down")
        result = rc.classify({RECORD: "ADDED"}, PATTERNS, read=broken, fclass=FCLASS)
        self.assertEqual(result["class"], rc.SEMANTIC_IMPLEMENTATION)

    def test_a_new_cs_file_is_an_implementation_not_a_comment_change(self):
        result = Repo({}, {HANDLER: b"// only a comment\n"}).classify({HANDLER: "ADDED"})
        self.assertEqual(result["class"], rc.SEMANTIC_IMPLEMENTATION)

    def test_a_deleted_cs_file_is_an_implementation(self):
        result = Repo({HANDLER: b"// only a comment\n"}, {}).classify({HANDLER: "DELETED"})
        self.assertEqual(result["class"], rc.SEMANTIC_IMPLEMENTATION)

    def test_an_unlisted_extension_on_the_surface_is_an_implementation(self):
        for path in (f"src/{NAME}/{NAME}.csproj", "tests/Fixtures/cases.json", f"src/{NAME}/notes.txt"):
            with self.subTest(path=path):
                self.assertEqual(Repo().classify({path: "MODIFIED"})["class"], rc.SEMANTIC_IMPLEMENTATION)

    def test_an_engine_whose_ownership_cannot_be_loaded_exempts_nothing(self):
        # mutation: treat an unplaceable path as the factory's
        repo = FactoryUpdate().repo()
        result = rc.classify(FactoryUpdate.paths(), PATTERNS, read=repo.read, fclass=lambda _path: None)
        self.assertEqual(result["class"], rc.SEMANTIC_IMPLEMENTATION)

    def test_a_policy_that_does_not_list_the_decisions_leaves_them_documentation(self):
        # The engine's own policy decides what is on the surface; the classifier only lowers within it.
        result = Repo({}, {RECORD: doc("# 0007\n")}).classify({RECORD: "ADDED"}, patterns=["src/**"])
        self.assertEqual(result["class"], rc.DOCUMENTATION)

    def test_a_decision_record_that_is_not_numbered_is_not_a_decision_record(self):
        result = Repo({}, {"docs/decisions/notes.json": b"{}"}).classify({"docs/decisions/notes.json": "ADDED"})
        self.assertEqual(result["class"], rc.SEMANTIC_IMPLEMENTATION)


class FactoryUpdate:
    """A factory update as the classifier sees one, with a knob for each thing it must notice moving."""

    def __init__(self, **changes):
        self.changes = changes

    @staticmethod
    def paths():
        return {"provenance.json": "MODIFIED", GENERATED: "MODIFIED", PROPS: "MODIFIED",
                f"src/{NAME}/packages.lock.json": "MODIFIED"}

    def repo(self):
        generated = b"// the registry, regenerated\n"
        base_args, head_args = {}, {"kernel": "1.0.0", "factory": "1.2.0"}
        for key, value in self.changes.items():
            if key.startswith("head_"):
                head_args[key[5:]] = value
        props = b"<Project />"
        before = record(generated={GENERATED: sha(b"// the registry\n"), PROPS: sha(b"<Project Old />")}, **base_args)
        after = record(generated={GENERATED: sha(self.changes.get("bytes", generated)), PROPS: sha(props)}, **head_args)
        head = {"provenance.json": json.dumps(after).encode(), GENERATED: self.changes.get("bytes", generated),
                PROPS: props, f"src/{NAME}/packages.lock.json": b"{}"}
        head.update(self.changes.get("extra", {}))
        return Repo({"provenance.json": json.dumps(before).encode()}, head)


class TestARegenerationIsInertOnlyWhenTheRulesDidNotMove(unittest.TestCase):
    """`generated-or-provenance` rests on one fact, and each way to break it is a case."""

    def classify(self, update, paths=None):
        return update.repo().classify(paths or FactoryUpdate.paths())

    def test_the_baseline_is_inert(self):
        self.assertEqual(self.classify(FactoryUpdate())["class"], rc.GENERATED_OR_PROVENANCE)

    def test_a_new_map_version_is_an_implementation(self):
        # mutation: compare the map's package id and not its version and digest
        result = self.classify(FactoryUpdate(head_maps=(("Pkg", "1.1.0", "bb"),)))
        self.assertEqual(result["class"], rc.SEMANTIC_IMPLEMENTATION)
        self.assertIn("maps", " ".join(result["reasons"]))

    def test_a_map_republished_under_the_same_version_is_an_implementation(self):
        result = self.classify(FactoryUpdate(head_maps=(("Pkg", "1.0.0", "bb"),)))
        self.assertEqual(result["class"], rc.SEMANTIC_IMPLEMENTATION)

    def test_a_moved_corpus_is_an_implementation(self):
        result = self.classify(FactoryUpdate(head_corpora=(("src1", "dd"),)))
        self.assertEqual(result["class"], rc.SEMANTIC_IMPLEMENTATION)

    def test_changed_randomness_is_an_implementation(self):
        result = self.classify(FactoryUpdate(head_randomness="pcg32"))
        self.assertEqual(result["class"], rc.SEMANTIC_IMPLEMENTATION)

    def test_a_dirty_factory_is_an_implementation(self):
        # mutation: do not read factory.dirty
        result = self.classify(FactoryUpdate(head_dirty=True))
        self.assertEqual(result["class"], rc.SEMANTIC_IMPLEMENTATION)

    def test_a_hand_written_file_voids_it(self):
        # mutation: judge only the generated files and ignore a handler in the same diff
        update = FactoryUpdate(extra={HANDLER: b"int F() { return 2; }"})
        paths = {**FactoryUpdate.paths(), HANDLER: "MODIFIED"}
        self.assertEqual(self.classify(update, paths)["class"], rc.SEMANTIC_IMPLEMENTATION)

    def test_an_overlay_row_voids_it(self):
        update = FactoryUpdate(extra={"overlay/x.json": b"{}"})
        paths = {**FactoryUpdate.paths(), "overlay/x.json": "MODIFIED"}
        self.assertEqual(self.classify(update, paths)["class"], rc.SEMANTIC_IMPLEMENTATION)

    def test_a_decision_record_in_the_diff_voids_it(self):
        update = FactoryUpdate(extra={RECORD: doc("# 0008\n")})
        paths = {**FactoryUpdate.paths(), RECORD: "ADDED"}
        self.assertEqual(self.classify(update, paths)["class"], rc.SEMANTIC_IMPLEMENTATION)

    def test_a_hand_edited_generated_file_is_an_implementation(self):
        # mutation: skip the check that the head bytes are the ones the head record hashes
        repo = FactoryUpdate().repo()
        repo.head[GENERATED] = b"// the registry, regenerated and then edited by hand\n"
        self.assertEqual(repo.classify(FactoryUpdate.paths())["class"], rc.SEMANTIC_IMPLEMENTATION)

    def test_a_regeneration_that_leaves_the_record_alone_is_an_implementation(self):
        # mutation: do not require provenance.json among the changed files
        paths = {p: c for p, c in FactoryUpdate.paths().items() if p != "provenance.json"}
        self.assertEqual(self.classify(FactoryUpdate(), paths)["class"], rc.SEMANTIC_IMPLEMENTATION)

    def test_an_unreadable_record_is_an_implementation(self):
        repo = FactoryUpdate().repo()
        repo.head["provenance.json"] = b"{ not json"
        self.assertEqual(repo.classify(FactoryUpdate.paths())["class"], rc.SEMANTIC_IMPLEMENTATION)

    def test_a_lock_file_without_the_pins_that_explain_it_is_an_implementation(self):
        # mutation: let a lock file move on its own
        paths = {p: c for p, c in FactoryUpdate.paths().items() if p != "RulesFactory.Packages.g.props"}
        self.assertEqual(self.classify(FactoryUpdate(), paths)["class"], rc.SEMANTIC_IMPLEMENTATION)

    def test_a_corpus_file_beside_a_regeneration_voids_it(self):
        # mutation: count `corpus/*`, a GENERATED row, as a file the factory writes. The record here hashes the
        # corpus file, as a real one does, and says the corpus is unmoved -- a hand edit and a record edited to match.
        update = FactoryUpdate(extra={"corpus/book.txt": b"an edited rule"})
        repo = update.repo()
        record_head = json.loads(repo.head["provenance.json"])
        record_head["generated"].append({"path": "corpus/book.txt", "sha256": sha(b"an edited rule")})
        repo.head["provenance.json"] = json.dumps(record_head).encode()
        paths = {**FactoryUpdate.paths(), "corpus/book.txt": "MODIFIED"}
        self.assertEqual(repo.classify(paths)["class"], rc.SEMANTIC_IMPLEMENTATION)

    def test_a_retired_path_is_not_the_factorys_to_delete_here(self):
        repo = FactoryUpdate().repo()
        paths = {**FactoryUpdate.paths(), "backlog/notes.md": "DELETED"}
        self.assertEqual(repo.classify(paths)["class"], rc.SEMANTIC_IMPLEMENTATION)

    def test_the_factory_and_the_kernel_may_move(self):
        # The point of a factory update. mutation: require them equal too, and no update is ever inert.
        result = self.classify(FactoryUpdate())
        self.assertIn("factory 1.1.0 -> 1.2.0", " ".join(result["reasons"]))
        self.assertIn("kernel 0.3.0 -> 1.0.0", " ".join(result["reasons"]))

    def test_managed_rails_alone_touch_no_surface_and_need_no_claim(self):
        repo = Repo({}, {"tools/pr-policy.py": b"# new"})
        result = repo.classify({"tools/pr-policy.py": "MODIFIED", "provenance.json": "MODIFIED"})
        self.assertEqual((result["class"], result["onSurface"]), (rc.GENERATED_OR_PROVENANCE, []))
        self.assertEqual(rc.judge(result, None)[0], rc.GENERATED_OR_PROVENANCE)


class TestCommentOnlyIsProvedNotAssumed(unittest.TestCase):
    """`documentation` for C# rests on a scanner, so each way it could be fooled is a case."""

    def same(self, before, after):
        return rc.comment_only(before.encode(), after.encode())

    def test_comments_and_spacing_are_not_code(self):
        self.assertTrue(self.same("int x = 1; // a", "int   x  =  1;\n\n/* b */\n"))
        self.assertTrue(self.same("a /*c*/ b", "a b"))

    def test_whether_there_is_space_between_tokens_is_kept_and_how_much_is_not(self):
        # Conservative on purpose: `x=1` and `x = 1` are the same program, and a scanner that says so
        # must also say `a+ ++b` and `a++ +b` are, which they are not.
        self.assertFalse(self.same("int x=1;", "int x = 1;"))

    def test_a_comment_is_a_separator_not_nothing(self):
        # mutation: delete comments instead of replacing them, so `a/*c*/b` becomes the one token `ab`
        self.assertFalse(self.same("ab", "a/*c*/b"))

    def test_a_changed_string_literal_is_code_even_when_it_looks_like_a_comment(self):
        # mutation: let `//` inside a literal start a comment
        self.assertFalse(self.same('var s = "http://a";', 'var s = "http://b";'))
        self.assertFalse(self.same('var s = "/* a */";', 'var s = "/* b */";'))

    def test_a_changed_verbatim_raw_or_interpolated_literal_is_code(self):
        self.assertFalse(self.same('var s = @"a // b";', 'var s = @"a // c";'))
        self.assertFalse(self.same('var s = """\n// a\n""";', 'var s = """\n// b\n""";'))
        self.assertFalse(self.same('var s = $"{x} // a";', 'var s = $"{x} // b";'))

    def test_a_changed_character_literal_is_code(self):
        self.assertFalse(self.same("var c = '/';", "var c = '*';"))
        self.assertFalse(self.same("var c = '\"'; // a", "var c = 'x'; // a"))

    def test_whitespace_inside_a_literal_is_code(self):
        # mutation: normalise whitespace in the literal as well
        self.assertFalse(self.same('var s = "a  b";', 'var s = "a b";'))

    def test_whether_two_tokens_are_separated_is_code(self):
        # `a + ++b` and `a++ + b` are different programs with the same tokens.
        self.assertFalse(self.same("x = a + ++b;", "x = a++ + b;"))

    def test_a_removed_statement_is_code(self):
        self.assertFalse(self.same("a(); b();", "a();"))

    def test_an_unterminated_comment_or_literal_is_unprovable(self):
        # mutation: treat an unterminated construct as running to the end and compare what is left
        self.assertFalse(self.same("a(); /* b", "a();"))
        self.assertFalse(self.same('a("b', 'a("b'.replace("b", "c")))
        self.assertIsNone(rc.code_signature("a(); /* never closed"))
        self.assertIsNone(rc.code_signature('s = "never closed'))

    def test_a_preprocessor_line_is_code(self):
        self.assertFalse(self.same("#if DEBUG\nx();\n#endif\n", "#if RELEASE\nx();\n#endif\n"))
        self.assertTrue(self.same("#region a b\nx();\n#endregion\n", "#region a b\nx(); // c\n#endregion\n"))

    def test_an_apostrophe_in_a_directive_does_not_desynchronise_the_scanner(self):
        before = "#region it's\nvar s = \"http://a\";\n#endregion\n"
        after = "#region it's\nvar s = \"http://b\";\n#endregion\n"
        self.assertFalse(self.same(before, after))

    def test_undecodable_bytes_are_unprovable(self):
        self.assertFalse(rc.comment_only(b"\xff", b"\xfe"))
        self.assertFalse(rc.comment_only(None, b"x"))


class TestWhatAPullRequestSays(unittest.TestCase):
    def body(self, line):
        # The comment is laid out as the template's own guidance is: a line that reads as a declaration.
        return ("## Linked issue\n\nCloses #1\n\n## Map and rules conformance\n\n"
                f"<!--\n     - review class: semantic-implementation\n-->\n{line}\n- entry id(s): none\n\n## Tests\n")

    def test_the_declared_class_is_read_from_the_conformance_section(self):
        self.assertEqual(rc.declared_class(self.body("- review class: decision-record-only")), "decision-record-only")
        self.assertEqual(rc.declared_class(self.body("* **Review class:** `documentation`")), "documentation")
        self.assertEqual(rc.declared_class(self.body("- review class: documentation. A README fix.")),
                         "documentation")
        self.assertEqual(rc.declared_class(self.body("- review class: `semantic-ruling`")), "semantic-ruling")

    def test_a_class_named_in_the_templates_own_comment_is_not_a_declaration(self):
        # mutation: read the raw body instead of the body with its HTML comments removed
        self.assertIsNone(rc.declared_class(self.body("- review class:")))

    def test_a_declaration_outside_the_conformance_section_is_not_read(self):
        body = "## Scope\n\n- review class: documentation\n\n## Map and rules conformance\n\n- entry id(s): x\n"
        self.assertIsNone(rc.declared_class(body))

    def test_a_repeated_conformance_section_is_read_as_pr_policy_reads_it(self):
        # mutation: concatenate the sections instead of letting the last one stand
        body = ("## Map and rules conformance\n\n- review class: documentation\n\n"
                "## Map and rules conformance\n\n- review class: decision-record-only\n")
        self.assertEqual(rc.declared_class(body), "decision-record-only")

    def test_a_decision_scope_is_read(self):
        body = self.body("- decision scope: the Story Mode victory rule")
        self.assertEqual(rc.declared_scope(body), "the Story Mode victory rule")
        self.assertIsNone(rc.declared_scope(self.body("- decision scope:")))


class TestTheRecordersNamesAreTheModulesClasses(unittest.TestCase):
    """`record-verdict.py` names the classes that owe no semantic review and cannot import the module that does."""

    def test_the_names_it_refuses_a_semantic_verdict_for_are_the_classes_that_owe_none(self):
        # mutation: add a class to reviewclass.py and not to the recorder, or the reverse
        import ast
        path = os.path.join(os.path.dirname(os.path.dirname(HERE)), "factory", "recipe", "rails", "tools",
                            "record-verdict.py")
        with open(path, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        named = next(ast.literal_eval(node.value.args[0]) for node in ast.walk(tree)
                     if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "NO_SEMANTIC_REVIEW")
        self.assertEqual(set(named), set(rc.CLASSES) - rc.SEMANTIC)
        self.assertEqual({c for c in rc.CLASSES if not rc.owes(c)["verdict"]}, set(named))


if __name__ == "__main__":
    unittest.main()
