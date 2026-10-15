#!/usr/bin/env python3
"""examples/can-spam/reference-check.py, proved able to fail (#667).

The script aligns the codified CAN-SPAM statute with the Act as enacted and gives every difference a
class by a named rule. A rule that cannot be watched failing is a rule that could be classing
anything, so each test below builds a small statute and a small Act by hand, states which rule
should fire, and then removes the thing the rule stands on -- the note, the source credit, the
reference -- and asserts that the difference falls to `potentially-substantive`.

The fixtures are written here, so a case does not move when a staged file does. The staged files
themselves are not in this repository; the last cases hold the committed JSON to the committed
report, and to its own rule table.

Run: python3 -m pytest tools/tests/test_can_spam_reference_check.py
"""
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
EXAMPLE = os.path.join(ROOT, "examples", "can-spam")

_spec = importlib.util.spec_from_file_location("reference_check", os.path.join(EXAMPLE, "reference-check.py"))
rc = importlib.util.module_from_spec(_spec)
sys.modules["reference_check"] = rc
_spec.loader.exec_module(rc)

NS = 'xmlns="http://xml.house.gov/schemas/uslm/1.0"'


def credit(act):
    return f"<sourceCredit>(Pub. L. 108–187, § {act}, Dec. 16, 2003, 117 Stat. 2699.)</sourceCredit>"


def section(code, act, body, notes="", heading=" Scope of the rule"):
    return (f'<section identifier="/us/usc/t15/s{code}"><num value="{code}">§ {code}.</num>'
            f'<heading>{heading}</heading>{body}'
            + (f"<notes>{notes}</notes>" if notes else "") + credit(act) + "</section>")


def subsection(code, letter, content, heading="", inner=""):
    h = f"<heading> {heading}</heading>" if heading else ""
    return (f'<subsection identifier="/us/usc/t15/s{code}/{letter}"><num value="{letter}">({letter})</num>{h}'
            f"<content>{content}</content>{inner}</subsection>")


def note(topic, *paragraphs):
    return f'<note topic="{topic}">' + "".join(f"<p>{p}</p>" for p in paragraphs) + "</note>"


def this_act_note(scope):
    return note("referencesInText",
                f"This chapter, referred to in {scope}, was in the original “this Act”, meaning Pub. L. 108–187.")


def chapter(*sections):
    xml = f'<chapter {NS} identifier="/us/usc/t15/ch103">' + "".join(sections) + "</chapter>"
    return rc.ET.fromstring(xml)


def act_raw(*sections):
    """The Act as the GPO prints it: each section is (number, heading, body)."""
    out = ["[108th Congress Public Law 187]", ""]
    for n, heading, body in sections:
        out.append(f"SEC. {n}. <<NOTE: 15 USC {7699 + n}.>> {heading}")
        out.append("")
        out.extend(body.split("\n"))
        out.append("")
    return "<html><body><pre>\n" + "\n".join(out) + "\n</pre></body></html>"


def compare(code_sections, act_sections):
    return rc.compare_statute(chapter(*code_sections), act_raw(*act_sections))


def records(code_sections, act_sections, **kw):
    _, _, recs = compare(code_sections, act_sections)
    return [r for r in recs if all(r[k] == v for k, v in kw.items())]


def one(code_body, act_body, notes="", heading=" Scope of the rule", act_heading="SCOPE OF THE RULE.", **kw):
    """The records of a one-section statute against a one-section Act."""
    return records([section(7701, 2, code_body, notes, heading)], [(2, act_heading, act_body)], **kw)


def head(code_heading, act_line):
    """Paragraph (a)'s heading records for a given heading in the file and a given line in the Act."""
    return one(subsection(7701, "a", "Rule.", code_heading), act_line, part="head", uslmIdentifier="/us/usc/t15/s7701/a")


def para(code_text, act_text, notes="", **kw):
    """Paragraph (a) with the given body text on each side; returns its body records."""
    return one(subsection(7701, "a", code_text, "Scope"),
               f"    (a) Scope.--{act_text}", notes, part="body", **kw)


def by_rule(recs):
    return sorted(r["rule"] for r in recs)


class TestAlignment(unittest.TestCase):
    def test_act_section_is_aligned_by_the_source_credit_not_by_number(self):
        # 5 -> 7709 and 9 -> 7704: no arithmetic on the numbers gives this
        alignment, _, recs = compare(
            [section(7709, 5, subsection(7709, "a", "Rule one.", "Scope")),
             section(7704, 9, subsection(7704, "a", "Rule “two”.", "Scope"))],
            [(5, "SCOPE OF THE RULE.", "    (a) Scope.--Rule one."),
             (9, "SCOPE OF THE RULE.", "    (a) Scope.--Rule ``two''.")])
        self.assertEqual([(a["actSection"], a["codifiedSection"]) for a in alignment], [(5, 7709), (9, 7704)])
        quotes = [r for r in recs if r["rule"] == "F-QUOTE-DOUBLE"]
        self.assertEqual({(r["actSection"], r["uslmIdentifier"]) for r in quotes}, {(9, "/us/usc/t15/s7704/a")})

    def test_a_difference_names_the_uslm_identifier_and_the_act_paragraph(self):
        recs = para("Rule “one”.", "Rule ``one''.")
        self.assertEqual(recs[0]["uslmIdentifier"], "/us/usc/t15/s7701/a")
        self.assertEqual(recs[0]["actSection"], 2)
        self.assertEqual(recs[0]["actParagraph"], "(a)")

    def test_a_section_without_source_credit_naming_the_act_is_refused(self):
        bad = section(7701, 2, subsection(7701, "a", "x", "Scope")).replace("Pub. L. 108–187, § 2", "Pub. L. 99-1")
        with self.assertRaises(rc.InputError):
            rc.Statute(chapter(bad))

    def test_nested_markers_are_aligned_by_their_chain(self):
        inner = ('<paragraph identifier="/us/usc/t15/s7701/a/1"><num value="1">(1)</num><content>First.</content></paragraph>'
                 '<paragraph identifier="/us/usc/t15/s7701/a/2"><num value="2">(2)</num><content>Second.</content></paragraph>')
        recs = one(subsection(7701, "a", "", "Scope", inner),
                   "    (a) Scope.--\n            (1) First.\n            (2) Seconds.", part="body")
        self.assertEqual([r["actParagraph"] for r in recs], ["(a)(2)"])
        self.assertEqual(recs[0]["rule"], "P-REMAINDER")

    def test_a_paragraph_only_the_act_has_is_one_difference_holding_all_of_it(self):
        inner = '<paragraph identifier="/us/usc/t15/s7701/a/1"><num value="1">(1)</num><content>First.</content></paragraph>'
        recs = one(subsection(7701, "a", "", "Scope", inner),
                   "    (a) Scope.--\n            (1) First.\n            (2) Second.", part="unit")
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["referenceText"], "(2) Second.")
        self.assertEqual(recs[0]["corpusText"], "")
        self.assertEqual(recs[0]["class"], rc.SUBSTANTIVE)

    def test_a_paragraph_only_the_file_has_is_one_difference_holding_all_of_it(self):
        inner = ('<paragraph identifier="/us/usc/t15/s7701/a/1"><num value="1">(1)</num><content>First.</content></paragraph>'
                 '<paragraph identifier="/us/usc/t15/s7701/a/2"><num value="2">(2)</num><content>Extra.</content></paragraph>')
        recs = one(subsection(7701, "a", "", "Scope", inner),
                   "    (a) Scope.--\n            (1) First.", part="unit")
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["corpusText"], "(2) Extra.")
        self.assertEqual(recs[0]["referenceText"], "")

    def test_a_marker_that_does_not_continue_its_sequence_stops_the_run(self):
        lines = ["    (a) First.", "    (c) Third, with (b) missing."]
        with self.assertRaises(rc.InputError):
            rc.act_units(lines)

    def test_a_numeric_marker_at_a_subsection_indent_is_a_paragraph_of_it(self):
        lines = ["    (a) Federal Law.--(1) Nothing in this Act", "impairs it.", "    (2) Nothing else."]
        self.assertEqual([p for p, _, _ in rc.act_units(lines)], [("a",), ("a", "1"), ("a", "2")])

    def test_a_marker_printed_inside_a_line_after_a_heading_opens_a_paragraph(self):
        lines = ["            (1) Inclusion.--(A) It is unlawful,", "        so.", "            (B) Not so."]
        self.assertEqual([p for p, _, _ in rc.act_units(lines)], [("1",), ("1", "A"), ("1", "B")])

    def test_two_markers_on_one_line_open_two_paragraphs(self):
        lines = ["                    (A) first;", "                    (B)(i) second; and", "                    (ii) third."]
        self.assertEqual([p for p, _, _ in rc.act_units(lines)], [("A",), ("B",), ("B", "i"), ("B", "ii")])

    def test_flush_text_after_a_nested_list_is_a_continuation_aligned_in_order(self):
        lines = ["                    (A) means--",
                 "                          (i) to provide--",
                 "                                    (I) one;",
                 "                                    (II) two,",
                 "                      a thing, which is set flush;",
                 "                          (ii) or three."]
        units = rc.act_units(lines)
        self.assertEqual([(p, k) for p, _, k in units][4:5], [(("~continuation", "1"), "continuation")])
        recs = records(
            [section(7701, 2, subsection(7701, "a", "means— x", "Scope"))],
            [(2, "SCOPE OF THE RULE.", "    (a) Scope.--means-- x")], part="unit")
        self.assertEqual(recs, [])

    def test_quoted_amendatory_text_is_not_read_for_markers(self):
        lines = ["    (a) Offense.--",
                 "            (1) In general.--Chapter 47 is amended by adding:",
                 "``Sec. 1037. Fraud",
                 "    ``(a) In General.--Whoever--",
                 "            ``(1) does it,",
                 "or conspires to do so.''.",
                 "    (b) Other.--Text."]
        self.assertEqual([p for p, _, _ in rc.act_units(lines)], [("a",), ("a", "1"), ("b",)])


class TestNormalization(unittest.TestCase):
    def test_line_breaks_and_runs_of_spaces_are_whitespace(self):
        self.assertEqual(para("The rule applies to all mail.", "The rule\n        applies   to all\n mail."), [])
        recs = para("The rule  applies\nto all mail.", "The rule\n        applies   to all\n mail. Extra.")
        self.assertEqual(recs[0]["corpusUnitText"], "(a) Scope The rule applies to all mail.")
        self.assertEqual(recs[0]["referenceUnitText"], "(a) Scope.--The rule applies to all mail. Extra.")

    def test_gpo_page_markers_and_note_insertions_are_markup(self):
        act = "The rule [[Page 117 STAT. 2700]] applies <<NOTE: 15 USC 7701.>> to mail."
        self.assertEqual(para("The rule applies to mail.", act), [])

    def test_a_section_s_notes_and_source_credit_are_not_its_text(self):
        notes = note("editorialNotes", "A note that the Act never says.")
        self.assertEqual(para("Rule.", "Rule.", notes), [])

    def test_a_word_added_is_a_difference_not_a_normalization(self):
        recs = para("The rule applies.", "The rule always applies.")
        self.assertEqual(by_rule(recs), ["P-REMAINDER"])
        self.assertEqual(recs[0]["referenceText"], "always")
        self.assertEqual(recs[0]["corpusText"], "")

    def test_case_in_a_body_is_a_difference(self):
        recs = para("The Rule applies.", "The rule applies.")
        self.assertEqual(by_rule(recs), ["P-REMAINDER"])

    def test_the_sides_digest_is_checked_before_anything_is_compared(self):
        with tempfile.TemporaryDirectory() as d:
            paths = []
            for name in ("zip", "act", "ecfr", "annual"):
                p = os.path.join(d, name)
                with open(p, "wb") as f:
                    f.write(b"not the staged file")
                paths.append(p)
            with self.assertRaises(rc.InputError) as cm:
                rc.build(*paths)
            self.assertIn("SHA-256", str(cm.exception))
            err = io.StringIO()
            with redirect_stderr(err):
                code = rc.main(["--uslm-zip", paths[0], "--act-html", paths[1], "--ecfr-xml", paths[2],
                                "--annual-xml", paths[3]])
            self.assertEqual(code, 2)

    def test_a_zip_with_another_member_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.zip")
            with zipfile.ZipFile(p, "w") as z:
                z.writestr("other.xml", "<a/>")
            with self.assertRaises(rc.InputError):
                rc.read_chapter(p, check=False)


class TestFormatting(unittest.TestCase):
    def assertRule(self, recs, rule):
        self.assertEqual(by_rule(recs), [rule], recs)
        self.assertEqual(recs[0]["class"], rc.FORMATTING)

    def test_double_quotes(self):
        recs = para("The term “mail” applies.", "The term ``mail'' applies.")
        self.assertEqual(by_rule(recs), ["F-QUOTE-DOUBLE", "F-QUOTE-DOUBLE"])

    def test_single_quotes_inside_double(self):
        recs = para("The term “‘mail’ box” applies.", "The term ```mail' box'' applies.")
        self.assertEqual(by_rule(recs), ["F-QUOTE-DOUBLE", "F-QUOTE-DOUBLE", "F-QUOTE-SINGLE", "F-QUOTE-SINGLE"])

    def test_apostrophe(self):
        self.assertRule(para("The sender’s mail.", "The sender's mail."), "F-APOSTROPHE")

    def test_an_apostrophe_is_not_a_quote_and_a_quote_is_not_an_apostrophe(self):
        recs = para("The ‘mail’ of the sender’s.", "The `mail' of the sender's.")
        self.assertEqual(by_rule(recs), ["F-APOSTROPHE", "F-QUOTE-SINGLE", "F-QUOTE-SINGLE"])

    def test_em_dash(self):
        self.assertRule(para("The rule—applies.", "The rule--applies."), "F-DASH-EM")

    def test_en_dash(self):
        self.assertRule(para("Sections 80a–1 apply.", "Sections 80a-1 apply."), "F-DASH-EN")

    def test_a_hyphen_for_an_em_dash_is_not_typography(self):
        recs = para("The rule—applies.", "The rule-applies.")
        self.assertEqual(by_rule(recs), ["P-REMAINDER"])

    def test_a_run_in_heading_delimiter(self):
        recs = head("Scope", "    (a) Scope.--Rule.")
        self.assertEqual(by_rule(recs), ["F-RUNIN-DELIM"])
        self.assertEqual(recs[0]["referenceText"], ".--")

    def test_a_heading_with_a_semicolon_is_still_a_heading(self):
        recs = head("Venue; service", "    (a) Venue; service.--Rule.")
        self.assertEqual(by_rule(recs), ["F-RUNIN-DELIM"])

    def test_heading_capitalisation(self):
        recs = head("Congressional determination of public policy",
                    "    (a) Congressional Determination of Public Policy.--Rule.")
        self.assertEqual(by_rule(recs), ["F-HEADCASE", "F-HEADCASE", "F-RUNIN-DELIM"])

    def test_the_sections_own_heading_in_capitals_and_its_closing_period(self):
        recs = records([section(7701, 2, subsection(7701, "a", "Rule.", "Scope"))],
                       [(2, "SCOPE OF THE RULE.", "    (a) Scope.--Rule.")], part="head", uslmIdentifier="/us/usc/t15/s7701")
        self.assertEqual(by_rule(recs), ["F-HEADCASE", "F-RUNIN-DELIM"])

    def test_a_different_word_in_a_heading_is_not_capitalisation(self):
        recs = head("Scope", "    (a) Reach.--Rule.")
        self.assertEqual(sorted(set(by_rule(recs))), ["F-RUNIN-DELIM", "P-REMAINDER"])

    def test_a_word_broken_at_a_line_end_is_the_word(self):
        recs = para("The subsection applies.", "The sub-\nsection applies.")
        self.assertEqual(by_rule(recs), ["F-HYPHENATION"])

    def test_a_hyphen_at_a_line_end_in_a_compound_stays_a_hyphen(self):
        self.assertEqual(para("The opt-out applies.", "The opt-\nout applies."), [])


class TestCodification(unittest.TestCase):
    NOTE_TEXT = "This chapter, referred to in text, was in the original “this Act”"

    def test_this_act_is_this_chapter_where_a_note_says_so(self):
        recs = para("Under this chapter it applies.", "Under this Act it applies.", this_act_note("text"))
        self.assertEqual(by_rule(recs), ["C-THIS-ACT"])
        self.assertEqual(recs[0]["class"], rc.CODIFICATION)
        ev = recs[0]["evidence"][0]
        self.assertEqual(ev["kind"], "note")
        self.assertIn("referencesInText", ev["location"])
        self.assertTrue(ev["quote"].startswith("This chapter, referred to in text"))

    def test_this_act_with_a_capital_is_the_same(self):
        recs = para("This chapter applies.", "This Act applies.", this_act_note("text"))
        self.assertEqual(by_rule(recs), ["C-THIS-ACT"])

    def test_without_the_note_this_chapter_for_this_act_is_potentially_substantive(self):
        recs = para("Under this chapter it applies.", "Under this Act it applies.")
        self.assertEqual(by_rule(recs), ["P-REMAINDER"])

    def test_a_note_that_covers_another_subsection_does_not_cover_this_one(self):
        recs = para("Under this chapter it applies.", "Under this Act it applies.", this_act_note("subsec. (b)"))
        self.assertEqual(by_rule(recs), ["P-REMAINDER"])

    def test_a_note_that_covers_this_subsection_does(self):
        recs = para("Under this chapter it applies.", "Under this Act it applies.",
                    this_act_note("subsecs. (b) and (a)"))
        self.assertEqual(by_rule(recs), ["C-THIS-ACT"])

    def test_the_scope_of_a_references_in_text_note_is_read(self):
        self.assertIsNone(rc.parse_scope("text"))
        self.assertEqual(rc.parse_scope("subsec. (a)(4)(A)(iv)"), [["a", "4", "A", "iv"]])
        self.assertEqual(rc.parse_scope("subsecs. (a) and (b)(1)"), [["a"], ["b", "1"]])
        self.assertEqual(rc.parse_scope("par. (1)"), [["1"]])
        self.assertEqual(rc.parse_scope("subsecs. (a) and (b)(3), (4)"), [["a"], ["b", "3"], ["b", "4"]])
        with self.assertRaises(rc.InputError):
            rc.parse_scope("the whole of it")

    def two_sections(self, act_text, code_text):
        """Section 7701 (Act 2) cites Act section 3, codified as 7702."""
        return (
            [section(7701, 2, subsection(7701, "a", code_text, "Scope")),
             section(7702, 3, subsection(7702, "a", "Other.", "Other"))],
            [(2, "SCOPE OF THE RULE.", f"    (a) Scope.--{act_text}"),
             (3, "OTHER RULE.", "    (a) Other.--Other.")])

    def test_a_reference_to_an_act_section_is_the_codified_section_its_source_credit_names(self):
        code, act = self.two_sections("As in section 3 of this Act.", "As in section 7702 of this title.")
        recs = records(code, act, part="body", uslmIdentifier="/us/usc/t15/s7701/a")
        self.assertIn("C-SECTION-NUMBER", by_rule(recs))
        rec = next(r for r in recs if r["rule"] == "C-SECTION-NUMBER")
        self.assertEqual((rec["referenceText"], rec["corpusText"]), ("3", "7702"))
        self.assertEqual(rec["evidence"][0]["kind"], "source-credit")
        self.assertIn("§ 3,", rec["evidence"][0]["quote"])
        self.assertEqual(rec["evidence"][0]["location"], "/us/usc/t15/s7702 sourceCredit")

    def test_a_section_number_the_credits_do_not_map_is_potentially_substantive(self):
        code, act = self.two_sections("As in section 3 of this Act.", "As in section 7711 of this title.")
        recs = records(code, act, part="body", uslmIdentifier="/us/usc/t15/s7701/a")
        self.assertNotIn("C-SECTION-NUMBER", by_rule(recs))
        self.assertIn("P-REMAINDER", by_rule(recs))

    def test_the_sections_designation(self):
        code, act = self.two_sections("Rule.", "Rule.")
        recs = records(code, act, part="num", uslmIdentifier="/us/usc/t15/s7701")
        self.assertEqual(by_rule(recs), ["C-SECTION-HEADING"])
        self.assertEqual((recs[0]["referenceText"], recs[0]["corpusText"]), ("SEC. 2.", "§ 7701."))
        self.assertIn("§ 2,", recs[0]["evidence"][0]["quote"])

    def test_a_designation_the_credit_does_not_state_is_potentially_substantive(self):
        bad = section(7701, 2, subsection(7701, "a", "Rule.", "Scope")).replace("§ 7701.", "§ 7799.")
        recs = records([bad], [(2, "SCOPE OF THE RULE.", "    (a) Scope.--Rule.")], part="num", uslmIdentifier="/us/usc/t15/s7701")
        self.assertEqual(by_rule(recs), ["P-REMAINDER"])

    def omitted(self, codification):
        notes = note("codification", codification) if codification else ""
        code = section(7703, 4, subsection(7703, "a", "", "Omitted") + subsection(7703, "b", "Kept.", "Kept"), notes)
        act = [(4, "PROHIBITION.", "\n".join([
            "    (a) Offense.--",
            "            (1) In general.--Chapter 47 of title 18 is amended.",
            "            (2) Conforming amendment.--The analysis is amended.",
            "    (b) Kept.--Kept."]))]
        return records([code], act)

    def test_an_omitted_subsection_is_the_act_subsection_a_codification_note_says_went_elsewhere(self):
        recs = self.omitted("Subsec. (a) of section 4 of Pub. L. 108–187 enacted section 1037 of Title 18.")
        rules = [(r["actParagraph"], r["part"], r["rule"]) for r in recs if r["rule"] == "C-OMITTED-SUBSECTION"]
        self.assertEqual(rules, [("(a)", "head", "C-OMITTED-SUBSECTION"), ("(a)(1)", "unit", "C-OMITTED-SUBSECTION"),
                                 ("(a)(2)", "unit", "C-OMITTED-SUBSECTION")])
        self.assertEqual({r["class"] for r in recs if r["rule"] == "C-OMITTED-SUBSECTION"}, {rc.CODIFICATION})
        ev = next(r for r in recs if r["rule"] == "C-OMITTED-SUBSECTION")["evidence"][0]
        self.assertIn("notes/note[@topic=codification]", ev["location"])
        self.assertIn("enacted section 1037 of Title 18", ev["quote"])

    def test_without_the_codification_note_an_omitted_subsection_is_potentially_substantive(self):
        recs = self.omitted(None)
        self.assertNotIn("C-OMITTED-SUBSECTION", by_rule(recs))
        self.assertEqual([r["rule"] for r in recs if r["part"] == "unit"], ["P-REMAINDER", "P-REMAINDER"])

    def test_a_note_about_another_subsection_does_not_omit_this_one(self):
        recs = self.omitted("Subsec. (b) of section 4 of Pub. L. 108–187 enacted section 1037 of Title 18.")
        self.assertNotIn("C-OMITTED-SUBSECTION", by_rule(recs))

    def test_an_act_section_the_chapter_has_no_section_for_is_codification_where_a_note_says_where_it_went(self):
        code = [section(7701, 2, subsection(7701, "a", "Rule.", "Scope"),
                        note("referencesInText", "Section 12 amended section 227 of Title 47, Telecommunications."))]
        act = [(2, "SCOPE OF THE RULE.", "    (a) Scope.--Rule."),
               (12, "RESTRICTIONS.", "    Section 227 of the Communications Act is amended.")]
        recs = records(code, act, actSection=12)
        self.assertEqual(by_rule(recs), ["C-ACT-SECTION-ELSEWHERE"])
        self.assertIn("Section 12 amended", recs[0]["evidence"][0]["quote"])

    def test_without_that_note_an_act_section_with_no_codified_section_is_potentially_substantive(self):
        code = [section(7701, 2, subsection(7701, "a", "Rule.", "Scope"))]
        act = [(2, "SCOPE OF THE RULE.", "    (a) Scope.--Rule."),
               (12, "RESTRICTIONS.", "    Section 227 of the Communications Act is amended.")]
        self.assertEqual(by_rule(records(code, act, actSection=12)), ["P-REMAINDER"])

    def test_sections_outside_two_to_fifteen_are_listed_and_not_compared(self):
        code = [section(7701, 2, subsection(7701, "a", "Rule.", "Scope"))]
        act = [(2, "SCOPE OF THE RULE.", "    (a) Scope.--Rule."), (16, "EFFECTIVE DATE.", "    Takes effect.")]
        _, unaligned, recs = compare(code, act)
        self.assertEqual([u["actSection"] for u in unaligned], [16])
        self.assertEqual([r for r in recs if r["actSection"] == 16], [])

    def test_a_footnote_set_in_the_body_is_the_codifiers_annotation(self):
        content = ('Any entity <ref idref="fn1">1</ref><note type="footnote"><num>1</num> So in original.</note> is subject.')
        recs = para(content, "Any entity is subject.")
        self.assertEqual(by_rule(recs), ["C-FOOTNOTE"])
        self.assertEqual(recs[0]["class"], rc.CODIFICATION)
        self.assertIn("So in original.", recs[0]["evidence"][0]["quote"])

    def test_a_date_put_for_the_date_of_enactment_is_not_codification_unless_the_file_says_so(self):
        recs = para("Not later than 6 months after December 16, 2003, it applies.",
                    "Not later than 6 months after the date of enactment of this Act, it applies.")
        self.assertEqual(by_rule(recs), ["P-REMAINDER"])
        self.assertEqual(recs[0]["referenceText"], "the date of enactment of this Act")
        self.assertEqual(recs[0]["corpusText"], "December 16, 2003")


class TestTextual(unittest.TestCase):
    def ref(self, href, text):
        return f'<ref href="{href}">{text}</ref>'

    def test_a_citation_of_another_acts_section_is_the_code_citation_of_the_same_section(self):
        content = "consistent with " + self.ref("/us/usc/t15/s45", "section 45 of this title") + "."
        recs = para(content, "consistent with section 5 of the Federal Trade Commission Act (15 U.S.C. 45).")
        self.assertEqual(by_rule(recs), ["T-CITATION-FORM"])
        self.assertEqual(recs[0]["class"], rc.TEXTUAL)
        self.assertEqual(recs[0]["referenceText"], "5 of the Federal Trade Commission Act (15 U.S.C. 45)")
        self.assertEqual(recs[0]["corpusText"], "45 of this title")
        kinds = [e["kind"] for e in recs[0]["evidence"]]
        self.assertEqual(kinds, ["reference-text", "ref"])
        self.assertEqual(recs[0]["evidence"][1]["href"], "/us/usc/t15/s45")

    def test_a_citation_without_a_reference_is_read_from_its_words(self):
        recs = para("under section 227 of title 47.", "under section 227 of the Communications Act of 1934 (47 U.S.C. 227).")
        self.assertEqual(by_rule(recs), ["T-CITATION-FORM"])
        self.assertEqual(recs[0]["evidence"][1]["kind"], "corpus-text")

    def test_a_citation_that_names_another_section_is_potentially_substantive(self):
        content = "consistent with " + self.ref("/us/usc/t15/s46", "section 46 of this title") + "."
        recs = para(content, "consistent with section 5 of the Federal Trade Commission Act (15 U.S.C. 45).")
        self.assertNotIn("T-CITATION-FORM", by_rule(recs))
        self.assertIn("P-REMAINDER", by_rule(recs))

    def test_of_this_title_after_a_cited_section_of_this_title(self):
        code = [section(7701, 2, subsection(7701, "a", "See " + self.ref("/us/usc/t15/s7702", "section 7702 of this title") + ".", "Scope")),
                section(7702, 3, subsection(7702, "a", "Other.", "Other"))]
        act = [(2, "SCOPE OF THE RULE.", "    (a) Scope.--See section 3."), (3, "OTHER RULE.", "    (a) Other.--Other.")]
        recs = records(code, act, part="body", uslmIdentifier="/us/usc/t15/s7701/a")
        self.assertEqual(by_rule(recs), ["C-SECTION-NUMBER", "T-OF-THIS-TITLE"])
        rec = next(r for r in recs if r["rule"] == "T-OF-THIS-TITLE")
        self.assertEqual(rec["class"], rc.TEXTUAL)
        self.assertEqual(rec["corpusText"], "of this title")
        self.assertEqual(rec["evidence"][0]["href"], "/us/usc/t15/s7702")

    def test_of_this_title_that_is_not_part_of_a_reference_is_potentially_substantive(self):
        code = [section(7701, 2, subsection(7701, "a", "See section 7702 of this title.", "Scope")),
                section(7702, 3, subsection(7702, "a", "Other.", "Other"))]
        act = [(2, "SCOPE OF THE RULE.", "    (a) Scope.--See section 3."), (3, "OTHER RULE.", "    (a) Other.--Other.")]
        recs = records(code, act, part="body", uslmIdentifier="/us/usc/t15/s7701/a")
        self.assertEqual(by_rule(recs), ["C-SECTION-NUMBER", "P-REMAINDER"])

    def test_of_this_act_for_of_this_title_in_a_citation_of_the_same_section(self):
        code = [section(7701, 2, subsection(7701, "a", "A violation of " + self.ref("/us/usc/t15/s7702", "section 7702 of this title") + ".", "Scope")),
                section(7702, 3, subsection(7702, "a", "Other.", "Other"))]
        act = [(2, "SCOPE OF THE RULE.", "    (a) Scope.--A violation of section 3 of this Act."), (3, "OTHER RULE.", "    (a) Other.--Other.")]
        recs = records(code, act, part="body", uslmIdentifier="/us/usc/t15/s7701/a")
        self.assertEqual(by_rule(recs), ["C-SECTION-NUMBER", "T-CITATION-QUALIFIER"])
        rec = next(r for r in recs if r["rule"] == "T-CITATION-QUALIFIER")
        self.assertEqual((rec["referenceText"], rec["corpusText"]), ("Act", "title"))

    def test_of_this_act_for_of_this_title_after_another_section_is_potentially_substantive(self):
        code = [section(7701, 2, subsection(7701, "a", "A violation of " + self.ref("/us/usc/t15/s7703", "section 7703 of this title") + ".", "Scope")),
                section(7702, 3, subsection(7702, "a", "Other.", "Other"))]
        act = [(2, "SCOPE OF THE RULE.", "    (a) Scope.--A violation of section 3 of this Act."), (3, "OTHER RULE.", "    (a) Other.--Other.")]
        recs = records(code, act, part="body", uslmIdentifier="/us/usc/t15/s7701/a")
        self.assertNotIn("T-CITATION-QUALIFIER", by_rule(recs))

    def test_united_states_code_after_a_title_the_file_resolves_to_the_code(self):
        content = "under " + self.ref("/us/usc/t18/s1037", "section 1037 of title 18") + " or title 18."
        recs = para(content, "under section 1037 of title 18, United States Code, or title 18.")
        self.assertEqual(by_rule(recs), ["T-UNITED-STATES-CODE"])
        self.assertEqual(recs[0]["referenceText"], ", United States Code,")
        self.assertEqual(recs[0]["evidence"][1]["href"], "/us/usc/t18/s1037")

    def test_united_states_code_after_a_title_the_file_never_resolves_is_potentially_substantive(self):
        recs = para("under title 49 by the Secretary.", "under title 49, United States Code, by the Secretary.")
        self.assertEqual(by_rule(recs), ["P-REMAINDER"])


class TestRegulation(unittest.TestCase):
    ECFR = ('<DIV5 N="316"><DIV8 N="316.9" TYPE="SECTION"><HEAD>§ 316.9 Scope.</HEAD>'
            '<P>This part   applies to <I>all</I> mail.</P></DIV8></DIV5>')
    ANNUAL = ('<CFRGRANULE><PART><SECTION><SECTNO>§ 316.9</SECTNO><SUBJECT>Scope.</SUBJECT>'
              '<P>This part applies to <E T="03">all</E>\n mail.</P></SECTION></PART></CFRGRANULE>')

    def test_whitespace_and_markup_are_not_differences(self):
        _, recs = rc.compare_regulation(self.ECFR.encode(), self.ANNUAL.encode())
        self.assertEqual(recs, [])

    def test_a_word_that_differs_is_a_difference(self):
        _, recs = rc.compare_regulation(self.ECFR.encode(), self.ANNUAL.replace("This part", "This Part").encode())
        self.assertEqual(len(recs), 1)
        self.assertEqual((recs[0]["corpusText"], recs[0]["referenceText"], recs[0]["class"]), ("part", "Part", rc.SUBSTANTIVE))
        self.assertEqual(recs[0]["scope"], "regulation")
        self.assertEqual(recs[0]["id"], "316.9/P1/body/1")

    def test_editions_that_do_not_hold_the_same_sections_are_refused(self):
        with self.assertRaises(rc.InputError):
            rc.compare_regulation(self.ECFR.encode(), self.ANNUAL.replace("316.9", "316.8").encode())


class TestTheDocument(unittest.TestCase):
    def test_a_comparison_repeated_is_the_same_comparison(self):
        code = [section(7701, 2, subsection(7701, "a", "Rule “one”, 80a–1.", "Scope"))]
        act = [(2, "SCOPE OF THE RULE.", "    (a) Scope.--Rule ``one'', 80a-1.")]
        self.assertEqual(json.dumps(compare(code, act)[2]), json.dumps(compare(code, act)[2]))

    def test_ids_are_unique_and_every_record_has_a_class_a_rule_and_both_texts(self):
        code = [section(7701, 2, subsection(7701, "a", "Rule “one”, 80a–1, and the sender’s.", "Scope"))]
        act = [(2, "SCOPE OF THE RULE.", "    (a) Scope.--Rule ``one'', 80a-1, and the sender's.")]
        recs = compare(code, act)[2]
        self.assertEqual(len({r["id"] for r in recs}), len(recs))
        for r in recs:
            self.assertIn(r["class"], rc.CLASSES)
            self.assertIn(r["rule"], rc.RULES)
            self.assertEqual(rc.RULES[r["rule"]][0], r["class"])
            self.assertTrue(r["evidence"] or r["class"] == rc.SUBSTANTIVE)
            self.assertIsNotNone(r["corpusText"])
            self.assertIsNotNone(r["referenceText"])

    def test_every_rule_in_the_table_is_applied_somewhere_in_this_file(self):
        source = open(__file__, encoding="utf-8").read()
        for rule in rc.RULES:
            self.assertIn(f'"{rule}"', source, f"{rule} is not asserted by any test")

    def test_the_report_is_written_from_the_json_and_checked_against_it(self):
        doc = {"schema": rc.SCHEMA, "inputs": [{"role": r, "file": n, "sha256": h, "describes": ""}
                                               for r, (n, h) in rc.EXPECTED.items()],
               "normalization": [{"id": i, "statement": t} for i, t in rc.NORMALIZATION],
               "rules": [{"id": i, "class": c, "statement": t} for i, (c, t) in rc.RULES.items()],
               "alignment": {"statute": [], "statuteUnaligned": [], "regulation": []},
               "differences": []}
        text = rc.render(doc)
        self.assertIn("Total: **0** differences.", text)
        with tempfile.TemporaryDirectory() as d:
            j, m = os.path.join(d, "d.json"), os.path.join(d, "r.md")
            with open(j, "w", encoding="utf-8") as f:
                json.dump(doc, f)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(rc.main(["--render", j, "--into", m]), 0)
                self.assertEqual(rc.main(["--render", j, "--check-report", m]), 0)
            with open(m, "a", encoding="utf-8") as f:
                f.write("edited by hand\n")
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(rc.main(["--render", j, "--check-report", m]), 1)


class TestTheCommittedDocument(unittest.TestCase):
    """REFERENCE-CHECK.md is the JSON's report; the JSON is internally consistent."""

    def setUp(self):
        with open(os.path.join(EXAMPLE, "reference-differences.json"), encoding="utf-8") as f:
            self.doc = json.load(f)

    def test_the_committed_report_is_the_report_of_the_committed_json(self):
        with open(os.path.join(EXAMPLE, "REFERENCE-CHECK.md"), encoding="utf-8") as f:
            self.assertEqual(f.read(), rc.render(self.doc))

    def test_the_committed_json_names_the_staged_files_by_digest(self):
        got = {i["role"]: i["sha256"] for i in self.doc["inputs"]}
        self.assertEqual(got, {r: h for r, (_, h) in rc.EXPECTED.items()})

    def test_every_difference_has_a_known_rule_of_its_class_and_ids_are_unique(self):
        diffs = self.doc["differences"]
        self.assertEqual(len({d["id"] for d in diffs}), len(diffs))
        for d in diffs:
            self.assertEqual(rc.RULES[d["rule"]][0], d["class"], d["id"])
            if d["class"] != rc.SUBSTANTIVE:
                self.assertTrue(d["evidence"], d["id"])
            if d["class"] == rc.CODIFICATION:
                self.assertTrue(all(e["kind"] in ("note", "source-credit", "footnote") and e["quote"] and e["location"]
                                    for e in d["evidence"]), d["id"])

    def test_the_counts_the_report_prints_are_the_counts_of_the_records(self):
        stat = [d for d in self.doc["differences"] if d["scope"] == "statute"]
        report = rc.render(self.doc)
        self.assertIn(f"Total: **{len(stat)}** differences.", report)


if __name__ == "__main__":
    unittest.main()
