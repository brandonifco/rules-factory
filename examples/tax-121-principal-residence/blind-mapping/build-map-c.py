#!/usr/bin/env python3
"""Write the reconciled map (Map C) from the first mapping and the adjudication record.

0014 says the map is corrected to the answers, and the two maps it was corrected from stay
where they are. This script is how the correction is auditable: it reads
`first-map.json` (Map A, frozen) and applies exactly the changes `resolutions.json`
rules, refusing to write if a change does not land. `blind-map.json` (Map B, frozen) is not
read at all -- every correction below is justified by a row of the record, not by copying an
entry across.

Map C is `../corpus-map.json`: the map this example publishes and anything is built from (#8).
Before it was promoted, Map A was that file and Map C sat here beside this script; both frozen
inputs now sit here instead, side by side, and what `--check` compares is the map in use. That
is the stronger reading of the same check -- a correction nobody ruled on cannot reach the
packed map without failing it -- and it is why Map A is a file and not only a git object: this
script has to read it.

Every change is keyed to a row id in resolutions.json. There are no others: a diff of Map C
against Map A that shows anything not listed here is a defect in this script.

  separate-from-the-dwelling-unit   allocation-required becomes clear, loses its ambiguity
                                    block, gains suspendedBy
  combined-sale-nets-dwelling-loss  a new entry on § 1.121-1(b)(4) Example 4, and examples-b's
                                    note says the paragraph is no longer declined whole
  worked-examples-as-entries        the two (c)(4) bounds go into short-temporary-absences'
                                    ambiguity question, not into entries of their own (#216)
  effective-date-gate               enabledBy: [effective-date] on every scope: in entry
  kind-two-year-equivalents         ownership-and-use-aggregation becomes a value
  kind-residence-exclusion          residence-excludes-personal-property becomes a value

Usage: python3 build-map-c.py [--check]
`--check` writes nothing and exits 1 if the committed map is not what this script builds.
"""
import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
MAP_A = HERE / "first-map.json"
MAP_C = HERE.parent / "corpus-map.json"


def by_id(document):
    return {entry["id"]: entry for entry in document["entries"]}


def build():
    document = json.loads(MAP_A.read_text(encoding="utf-8"))
    entries = by_id(document)
    landed = []

    # --- separate-from-the-dwelling-unit -----------------------------------------------
    allocation = entries["allocation-required"]
    assert allocation["clarity"] == "ambiguous" and "ambiguity" in allocation
    allocation["clarity"] = "clear"
    del allocation["ambiguity"]
    allocation["suspendedBy"] = ["no-allocation-within-dwelling-unit"]
    allocation["note"] = (
        "One rule in two sentences: the second begins \"Thus\" and restates the first as a "
        "consequence, so they are one span and one entry. The term that decides the rule is "
        "\"separate from the dwelling unit\", and the corpus states the test for it in this "
        "paragraph's own third sentence -- no allocation is required where both portions are "
        "within the same dwelling unit -- with (e)(2) closing the partition from the other side "
        "by subtracting appurtenant structures and other property from the term. So the relation "
        "is fixed and the term is not: its content is section 280A(f)(1)'s, in a corpus that was "
        "not admitted, which is why this entry declines through dwelling-unit-definition with "
        "MissingRulesData rather than carrying an ambiguity of its own. The first mapping "
        "recorded it ambiguous and the blind mapping recorded it clear because (e)(2) names a "
        "definition; both stopped before the third sentence. See blind-mapping/resolutions.json, "
        "row separate-from-the-dwelling-unit. A test must show a portion inside the dwelling unit "
        "and a portion outside it, and must show the decline where the meaning of the term is "
        "what the case turns on."
    )
    landed.append("separate-from-the-dwelling-unit")

    # --- combined-sale-nets-dwelling-loss ----------------------------------------------
    assert "combined-sale-nets-dwelling-loss" not in entries
    netting = {
        "id": "combined-sale-nets-dwelling-loss",
        "name": "A loss on one of two combined transactions and the excludable gain",
        "locator": {"sourceId": "cfr-26-1.121-1", "citation": "§ 1.121-1(b)(4) Example 4"},
        "kind": "operation",
        "scope": "in",
        "clarity": "ambiguous",
        "ambiguity": {
            "question": "Example 4 excludes $245,000 where the house and 1 acre were sold at a "
                        "$25,000 loss and the 29 acres of vacant land realized $270,000 of gain: "
                        "the loss is netted against the gain, and the $250,000 maximum limitation "
                        "amount is not what produces the figure. No sentence of paragraph "
                        "(b)(3)(ii) says that a loss on one of the two transactions reduces the "
                        "gain excludable on the other. What it says is that the two are treated "
                        "as one sale or exchange \"For purposes of section 121(b)(1) and (2) "
                        "(relating to the maximum limitation amount of the section 121 "
                        "exclusion)\", which is a merger bounded to the cap. The example fixes "
                        "the answer for D's figures and states no rule, so the corpus determines "
                        "one answer for this fact pattern and none for any other pair of figures.",
            "fate": "unresolved",
            "unresolvedReason": "RequiresInterpretation",
        },
        "dependsOn": ["vacant-land-single-sale", "maximum-limitation-amount"],
        "enabledBy": ["effective-date"],
        "evidence": "In 2003 D sells the house and 1 acre and the 29 acres in 2 separate "
                    "transactions. D sells the house and 1 acre at a loss of $25,000. D realizes "
                    "$270,000 of gain from the sale of the 29 acres. D may exclude the $245,000 "
                    "gain from the 2 sales.",
        "status": "mapped",
        "note": "Mapped in scope against the rest of (b)(4), which stays declined, because scope "
                "is decided per rule and never per paragraph. The blind second mapping found this "
                "and the first mapping did not: every locator in the first map resolves, its "
                "extent is reached and it passes its publish gate, and no entry in it can produce "
                "$245,000. A test must show the two transactions netted and must show the engine "
                "declining on any figures but D's.",
    }
    position = [i for i, e in enumerate(document["entries"]) if e["id"] == "examples-b"][0]
    document["entries"].insert(position + 1, netting)
    entries = by_id(document)
    entries["examples-b"]["note"] = (
        "Read and declined, rule by rule rather than as a paragraph. Examples 1, 2 and 3 apply "
        "rules (b)(1) to (b)(3) state and state no rule of their own; every number in them is an "
        "output of an entry this map already has, which makes them the slice's test suite and "
        "Phase 6 is where they belong. Example 4 is not declined: it nets a $25,000 loss on the "
        "dwelling unit against $270,000 of gain on the vacant land and no operative sentence says "
        "a loss does that, so it is mapped in scope as combined-sale-nets-dwelling-loss. The "
        "first mapping declined all four, partly because the eCFR XML puts them in <EXAMPLE> "
        "elements the locator checker did not index, so no entry could cite one; the checker now "
        "indexes them and `§ 1.121-1(b)(4) Example 4` is a citation it verifies. The pointer "
        "\"this paragraph (b)\" names one paragraph holding fourteen of this map's entries, and "
        "`crossReferences` resolves one pointer to one entry, so the three sub-paragraph heads "
        "are declared with the same `cites` three times."
    )
    landed.append("combined-sale-nets-dwelling-loss")

    # --- worked-examples-as-entries (#216, closed by 0031: the bounds are `ambiguity.bounds`) ---
    absences = entries["short-temporary-absences"]
    absences["ambiguity"]["question"] = (
        "\"Short temporary absences\" fixes no length and no test. The corpus gives two instances "
        "-- a vacation and a seasonal absence -- introduced by \"such as\", so they bound nothing, "
        "and names nobody to decide. Paragraph (c)(4)'s worked examples bound the term at its two "
        "ends and at no point between them, and are recorded in `bounds` below: a 1-year "
        "sabbatical leave is not a short temporary absence (Example 4) and a 2-month vacation is "
        "one (Example 5). An absence of five months is inside neither, and the corpus says nothing "
        "about it."
    )
    absences["ambiguity"]["bounds"] = {
        "term": "short temporary absences",
        "dimension": "duration",
        "examples": [
            {
                "locator": {"sourceId": "cfr-26-1.121-1", "citation": "§ 1.121-1(c)(4) Example 4"},
                "text": "He uses the house as his principal residence continuously until September "
                        "1, 1998, when he goes abroad for a 1-year sabbatical leave. On October 1, "
                        "1999, 1 month after returning from the leave, D sells the house. Because "
                        "his leave is not considered to be a short temporary absence under "
                        "paragraph (c)(2) of this section, the period of the sabbatical leave may "
                        "not be included in determining whether D used the house for periods "
                        "aggregating 2 years during the 5-year period ending on the date of the "
                        "sale.",
                "verdict": "doesNotApply",
                "value": "P1Y",
            },
            {
                "locator": {"sourceId": "cfr-26-1.121-1", "citation": "§ 1.121-1(c)(4) Example 5"},
                "text": "During 1998 and 1999, E leaves his residence for a 2-month summer "
                        "vacation. E sells the house on March 1, 2000. Although, in the 5-year "
                        "period preceding the date of sale, the total time E used his residence is "
                        "less than 2 years (21 months), the section 121 exclusion will apply to "
                        "gain from the sale of the residence because, under paragraph (c)(2) of "
                        "this section, the 2-month vacations are short temporary absences and are "
                        "counted as periods of use in determining whether E used the residence for "
                        "the requisite period.",
                "verdict": "applies",
                "value": "P2M",
            },
        ],
    }
    absences["note"] = (
        "The two worked examples are the corpus's only authority on the term and they answer no "
        "caller's request: what they do is constrain which readings of this rule are permissible. "
        "They are recorded as `ambiguity.bounds` rather than as entries of their own -- the blind "
        "second mapping made each an ordinary in-scope entry and kept this one ambiguous, which "
        "preserves the authority and loses the relation (#216, closed by rules-factory decision "
        "0031). An owner's ruling on this question under 0027 states the line it draws in the same "
        "dimension, and one that would make a 1-year sabbatical short is refused by the engine's "
        "own gate, naming Example 4. What the entry itself determines is that a qualifying absence "
        "is counted even where the residence was rented out."
    )
    entries["examples-c"]["note"] = (
        entries["examples-c"]["note"].rstrip()
        + " Examples 4 and 5 are the two the corpus needs read: each states that a particular "
          "absence is or is not a short temporary absence, which the operative text does not. They "
          "are declined here as entries -- an example that bounds a term an operative rule leaves "
          "open is not an entry -- and carried as `ambiguity.bounds` on short-temporary-absences, "
          "where a later ruling is compared against them (#216, decision 0031)."
    )
    landed.append("worked-examples-as-entries")

    # --- kind-two-year-equivalents and kind-residence-exclusion -------------------------
    aggregation = entries["ownership-and-use-aggregation"]
    assert aggregation["kind"] == "operation"
    aggregation["kind"] = "value"
    aggregation["note"] = (
        "The corpus's own arithmetic, and a value rather than an operation: the constituent "
        "supplies three equivalent quantities -- 2 years, 24 full months, 730 days -- and states "
        "no procedure the engine performs. The procedure that consumes them is "
        "ownership-and-use-test, which § 1.121-1(a) states and this map already carries. A test "
        "must show 24 months, 730 days, and 729 days."
    )
    exclusion = entries["residence-excludes-personal-property"]
    assert exclusion["kind"] == "operation"
    exclusion["kind"] = "value"
    exclusion["note"] = (
        exclusion["note"].rstrip()
        + " Recorded as a value, matching residence-may-include one sentence earlier: \"may "
          "include\" and \"does not include\" state the extension of the same term from opposite "
          "ends, and the first mapping classified them differently."
    )
    landed.append("kind-two-year-equivalents")
    landed.append("kind-residence-exclusion")

    # --- effective-date-gate ------------------------------------------------------------
    gated = 0
    for entry in document["entries"]:
        if entry["scope"] != "in" or entry["id"] == "effective-date":
            continue
        if "effective-date" in entry.get("enabledBy", []):
            continue
        entry["enabledBy"] = sorted(set(entry.get("enabledBy", [])) | {"effective-date"})
        gated += 1
    assert gated >= 30, gated
    entries["effective-date"]["note"] = (
        entries["effective-date"]["note"].rstrip()
        + " Every scope: in entry of this map names it in `enabledBy`: the sentence says \"This "
          "section is applicable\", so it is a rule that makes every rule of the section reachable "
          "and 0011 puts that in `enabledBy`. The first mapping recorded the gate and none of its "
          "reach, which is the omission the blind second mapping found most of."
    )
    landed.append("effective-date-gate")

    # No `about` field: the map envelope is closed (schemaVersion, corpus, baseline, extent,
    # entries) and check-map.py refuses an unknown one. What this map is, and which single
    # disagreement it does not carry, is README.md's job.
    return document, landed, gated


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true",
                        help="write nothing; fail if the committed map differs")
    arguments = parser.parse_args()

    document, landed, gated = build()
    text = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
    if arguments.check:
        if not MAP_C.is_file():
            print(f"{MAP_C} does not exist", file=sys.stderr)
            return 1
        if MAP_C.read_text(encoding="utf-8") != text:
            print(f"{MAP_C} is not what build-map-c.py builds from first-map.json",
                  file=sys.stderr)
            return 1
        print(f"corpus-map.json is what build-map-c.py builds from first-map.json "
              f"({len(document['entries'])} entries)")
        return 0
    MAP_C.write_text(text, encoding="utf-8")
    print(f"wrote {MAP_C}: {len(document['entries'])} entries, "
          f"{len(landed)} resolution(s) applied, {gated} entries gated on effective-date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
