#!/usr/bin/env python3
"""Build blind-map.json for cfr-14-107 subpart B slice, and verify it."""
import html, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = "cfr-14-107"
RI = "RequiresInterpretation"


def loc(c):
    return {"sourceId": SRC, "citation": c}


def gap(q):
    return {"question": q, "fate": "unresolved", "unresolvedReason": RI}


def E(id, name, citation, kind, evidence, clarity="clear", ambiguity=None, dependsOn=None,
      enabledBy=None, suspendedBy=None, definedElsewhere=None, crossReferences=None, note=None):
    e = {"id": id, "name": name, "locator": loc(citation), "kind": kind, "scope": "in",
         "clarity": clarity}
    if ambiguity:
        e["ambiguity"] = ambiguity
    e["dependsOn"] = dependsOn or []
    if enabledBy:
        e["enabledBy"] = enabledBy
    if suspendedBy:
        e["suspendedBy"] = suspendedBy
    if definedElsewhere:
        e["definedElsewhere"] = {"reference": definedElsewhere}
    if crossReferences:
        e["crossReferences"] = crossReferences
    e["evidence"] = evidence
    e["status"] = "mapped"
    if note:
        e["note"] = note
    return e


OUTSIDE = "Target is in part 107 but outside this map's extent (the slice); no entry exists here."
WAIVER_NOTE = ("A certificate of waiver under § 107.200 may authorize deviation from this rule; "
               "the waiver rules are outside the extent, so no suspendedBy edge can be recorded.")

entries = [
    # § 107.25
    E("no-operation-from-moving-aircraft", "Operation from a moving aircraft",
      "§ 107.25 introductory text, (a)", "operation",
      "No person may operate a small unmanned aircraft system— (a) From a moving aircraft;",
      note="Prohibition without exception. Whether the aircraft is moving is a caller-supplied parameter. " + WAIVER_NOTE),
    E("no-operation-from-moving-vehicle", "Operation from a moving land or water-borne vehicle",
      "§ 107.25(b)", "operation",
      "(b) From a moving land or water-borne vehicle unless the small unmanned aircraft is flown over a sparsely populated area and is not transporting another person's property for compensation or hire.",
      clarity="ambiguous",
      ambiguity=gap("'Sparsely populated area' is not defined in the slice or § 107.3 and no measure is stated; the corpus does not fix when an area qualifies."),
      note="Both exception limbs must hold. Whether property of another is carried for compensation or hire is a parameter. "
           "Test must show: vehicle stationary (rule not engaged), moving with both limbs met, moving with each limb failing. " + WAIVER_NOTE),

    # § 107.29
    E("night-operation-conditions", "Operation at night", "§ 107.29(a)", "operation",
      "(a) Except as provided in paragraph (d) of this section, no person may operate a small unmanned aircraft system at night unless—",
      dependsOn=["night-rpic-knowledge-currency", "night-anti-collision-lighting"],
      definedElsewhere="cfr-14-1.1",
      crossReferences=[{"cites": "paragraph (d) of this section", "resolvedBy": "night-waiver-operation-bar"}],
      note="'Night' is not defined in § 107.3; § 107.3 defers undefined terms to § 1.1 of this chapter, which is not admitted. "
           "Both (a)(1) and (a)(2) must hold."),
    E("night-rpic-knowledge-currency", "Remote pilot knowledge test or training for night operation",
      "§ 107.29(a)(1)", "operation",
      "(1) The remote pilot in command of the small unmanned aircraft has completed an initial knowledge test or training, as applicable, under § 107.65 after April 6, 2021; and",
      clarity="ambiguous",
      ambiguity=gap("Whether 'initial' qualifies 'training' as well as 'knowledge test' is not settled, and 'as applicable' points into § 107.65, whose paragraphs name an initial aeronautical knowledge test, recurrent training and training for part 61 certificate holders; which of those satisfy (a)(1) is not fixed by the slice."),
      crossReferences=[{"cites": "§ 107.65", "unmapped": OUTSIDE}],
      note="Completion date is a parameter compared against April 6, 2021 (strictly after)."),
    E("night-anti-collision-lighting", "Anti-collision lighting required at night", "§ 107.29(a)(2)", "operation",
      "(2) The small unmanned aircraft has lighted anti-collision lighting visible for at least 3 statute miles that has a flash rate sufficient to avoid a collision.",
      dependsOn=["anti-collision-visibility-night", "anti-collision-flash-rate-night"],
      note="Lighting must be lighted, meet the visibility figure, and meet the flash-rate standard. " + WAIVER_NOTE),
    E("anti-collision-visibility-night", "Anti-collision lighting visibility distance (night)", "§ 107.29(a)(2)", "value",
      "lighted anti-collision lighting visible for at least 3 statute miles",
      note="Minimum 3 statute miles, inclusive."),
    E("anti-collision-flash-rate-night", "Anti-collision flash rate sufficient to avoid a collision (night)", "§ 107.29(a)(2)", "assertion",
      "that has a flash rate sufficient to avoid a collision",
      note="Delegated standard; measure quoted: 'sufficient to avoid a collision'. Demand, attribute, record, never infer."),
    E("night-lighting-intensity-reduction", "Reducing anti-collision lighting intensity (night)", "§ 107.29(a)(2)", "operation",
      "The remote pilot in command may reduce the intensity of, but may not extinguish, the anti-collision lighting if he or she determines that, because of operating conditions, it would be in the interest of safety to do so.",
      dependsOn=["night-lighting-safety-determination"], enabledBy=["night-anti-collision-lighting"],
      note="Reduction permitted only on the determination; extinguishing is never permitted."),
    E("night-lighting-safety-determination", "Remote pilot's safety determination to reduce lighting (night)", "§ 107.29(a)(2)", "assertion",
      "if he or she determines that, because of operating conditions, it would be in the interest of safety to do so",
      note="The remote pilot in command's determination is operative; measure quoted: 'because of operating conditions ... in the interest of safety'."),
    E("twilight-operation-lighting", "Operation during civil twilight", "§ 107.29(b)", "operation",
      "(b) No person may operate a small unmanned aircraft system during periods of civil twilight unless the small unmanned aircraft has lighted anti-collision lighting visible for at least 3 statute miles that has a flash rate sufficient to avoid a collision.",
      dependsOn=["anti-collision-visibility-twilight", "anti-collision-flash-rate-twilight"],
      enabledBy=["civil-twilight-morning", "civil-twilight-evening", "civil-twilight-alaska"],
      note="Reachable only during a period that one of the civil-twilight definitions in (c) covers. " + WAIVER_NOTE),
    E("anti-collision-visibility-twilight", "Anti-collision lighting visibility distance (civil twilight)", "§ 107.29(b)", "value",
      "lighted anti-collision lighting visible for at least 3 statute miles",
      note="Same figure as the night rule, stated separately in (b)."),
    E("anti-collision-flash-rate-twilight", "Anti-collision flash rate sufficient to avoid a collision (civil twilight)", "§ 107.29(b)", "assertion",
      "that has a flash rate sufficient to avoid a collision",
      note="Measure quoted: 'sufficient to avoid a collision'."),
    E("twilight-lighting-intensity-reduction", "Reducing anti-collision lighting intensity (civil twilight)", "§ 107.29(b)", "operation",
      "The remote pilot in command may reduce the intensity of, but may not extinguish, the anti-collision lighting if he or she determines that, because of operating conditions, it would be in the interest of safety to do so.",
      dependsOn=["twilight-lighting-safety-determination"], enabledBy=["twilight-operation-lighting"]),
    E("twilight-lighting-safety-determination", "Remote pilot's safety determination to reduce lighting (civil twilight)", "§ 107.29(b)", "assertion",
      "if he or she determines that, because of operating conditions, it would be in the interest of safety to do so",
      note="Measure quoted: 'because of operating conditions ... in the interest of safety'."),
    E("civil-twilight-morning", "Morning civil twilight outside Alaska", "§ 107.29(c), (c)(1)", "value",
      "(c) For purposes of paragraph (b) of this section, civil twilight refers to the following: (1) Except for Alaska, a period of time that begins 30 minutes before official sunrise and ends at official sunrise;",
      crossReferences=[{"cites": "paragraph (b) of this section", "resolvedBy": "twilight-operation-lighting"}],
      note="Official sunrise time and location are parameters. Boundaries: 30 minutes before sunrise through sunrise; endpoint inclusivity is not stated."),
    E("civil-twilight-evening", "Evening civil twilight outside Alaska", "§ 107.29(c)(2)", "value",
      "(2) Except for Alaska, a period of time that begins at official sunset and ends 30 minutes after official sunset; and",
      note="Official sunset time is a parameter."),
    E("civil-twilight-alaska", "Civil twilight in Alaska", "§ 107.29(c)(3)", "value",
      "(3) In Alaska, the period of civil twilight as defined in the Air Almanac.",
      definedElsewhere="air-almanac",
      crossReferences=[{"cites": "as defined in the Air Almanac", "unmapped": "The Air Almanac is not an admitted corpus; see definedElsewhere."}]),
    E("night-waiver-operation-bar", "No night operation under pre-April 21, 2021 waivers after May 17, 2021", "§ 107.29(d)", "operation",
      "(d) After May 17, 2021, no person may operate a small unmanned aircraft system at night in accordance with a certificate of waiver issued prior to April 21, 2021 under § 107.200.",
      definedElsewhere="cfr-14-1.1",
      crossReferences=[{"cites": "§ 107.200", "unmapped": OUTSIDE}],
      note="Dates are parameters (operation date, waiver issue date). Still in force although every current operation date is after May 17, 2021."),
    E("night-waiver-termination", "Termination of pre-March 16, 2021 night waivers", "§ 107.29(d)", "operation",
      "The certificates of waiver issued prior to March 16, 2021 under § 107.200 that authorize deviation from § 107.29 terminate on May 17, 2021.",
      crossReferences=[{"cites": "§ 107.200", "unmapped": OUTSIDE},
                       {"cites": "§ 107.29", "resolvedBy": "night-operation-conditions"}],
      note="Waivers issued between March 16 and April 21, 2021 are barred for night use by the first sentence but are not terminated by this one; a test should show both date bands."),

    # § 107.31
    E("vlos-ability", "Visual line of sight ability", "§ 107.31(a), (a)(1), (a)(2), (a)(3), (a)(4)", "assertion",
      "(a) With vision that is unaided by any device other than corrective lenses, the remote pilot in command, the visual observer (if one is used), and the person manipulating the flight control of the small unmanned aircraft system must be able to see the unmanned aircraft throughout the entire flight in order to: (1) Know the unmanned aircraft's location; (2) Determine the unmanned aircraft's attitude, altitude, and direction of flight; (3) Observe the airspace for other air traffic or hazards; and (4) Determine that the unmanned aircraft does not endanger the life or property of another.",
      note="Being 'able to see' is measured against the four stated purposes ('in order to: ...'), so it is an assertion for each named person. "
           "'Corrective lenses' is defined in § 107.3 (spectacles or contact lenses). " + WAIVER_NOTE),
    E("vlos-exercised-by", "Who exercises visual line of sight", "§ 107.31(b), (b)(1), (b)(2)", "operation",
      "(b) Throughout the entire flight of the small unmanned aircraft, the ability described in paragraph (a) of this section must be exercised by either: (1) The remote pilot in command and the person manipulating the flight controls of the small unmanned aircraft system; or (2) A visual observer.",
      dependsOn=["vlos-ability"],
      crossReferences=[{"cites": "paragraph (a) of this section", "resolvedBy": "vlos-ability"}],
      note="Closed disjunction; which branch was used is a parameter."),

    # § 107.33
    E("vo-effective-communication", "Effective communication with the visual observer", "§ 107.33 introductory text, (a)", "operation",
      "If a visual observer is used during the aircraft operation, all of the following requirements must be met: (a) The remote pilot in command, the person manipulating the flight controls of the small unmanned aircraft system, and the visual observer must maintain effective communication with each other at all times.",
      clarity="ambiguous",
      ambiguity=gap("'Effective' communication states no measure; the corpus does not fix what communication qualifies."),
      note="Applies only when a visual observer is used, which is a parameter, not a rule; hence no enabledBy. " + WAIVER_NOTE),
    E("vo-able-to-see", "Remote pilot ensures visual observer can see the aircraft", "§ 107.33(b)", "operation",
      "(b) The remote pilot in command must ensure that the visual observer is able to see the unmanned aircraft in the manner specified in § 107.31.",
      dependsOn=["vlos-ability"],
      crossReferences=[{"cites": "§ 107.31", "resolvedBy": "vlos-ability"}],
      note="Same visual-observer-used condition as vo-effective-communication."),
    E("vo-coordinated-scan-and-awareness", "Coordinated airspace scan and position awareness", "§ 107.33(c), (c)(1), (c)(2)", "assertion",
      "(c) The remote pilot in command, the person manipulating the flight controls of the small unmanned aircraft system, and the visual observer must coordinate to do the following: (1) Scan the airspace where the small unmanned aircraft is operating for any potential collision hazard; and (2) Maintain awareness of the position of the small unmanned aircraft through direct visual observation.",
      note="Measures quoted: scan 'for any potential collision hazard'; awareness 'through direct visual observation'. Same visual-observer-used condition."),

    # § 107.35
    E("one-aircraft-per-person", "Operation of multiple small unmanned aircraft", "§ 107.35", "operation",
      "A person may not manipulate flight controls or act as a remote pilot in command or visual observer in the operation of more than one unmanned aircraft at the same time.",
      note="Counts per person across all three roles; one aircraft is allowed, two simultaneously is not. " + WAIVER_NOTE),

    # § 107.36
    E("no-hazardous-material", "Carriage of hazardous material", "§ 107.36", "operation",
      "A small unmanned aircraft may not carry hazardous material. For purposes of this section, the term hazardous material is defined in 49 CFR 171.8.",
      definedElsewhere="cfr-49-171.8",
      crossReferences=[{"cites": "49 CFR 171.8", "unmapped": "49 CFR 171.8 is not an admitted corpus; see definedElsewhere."}],
      note="Not listed as waivable in § 107.205 (outside extent)."),

    # § 107.37
    E("yield-right-of-way", "Yielding the right of way", "§ 107.37(a)", "operation",
      "(a) Each small unmanned aircraft must yield the right of way to all aircraft, airborne vehicles, and launch and reentry vehicles.",
      dependsOn=["yield-meaning"],
      note="Class of the other vehicle is a parameter. " + WAIVER_NOTE),
    E("yield-meaning", "What yielding the right of way means", "§ 107.37(a)", "operation",
      "Yielding the right of way means that the small unmanned aircraft must give way to the aircraft or vehicle and may not pass over, under, or ahead of it unless well clear.",
      clarity="ambiguous",
      ambiguity=gap("'Well clear' is not defined and no distance or measure is stated."),
      note="Definition stated as conduct: give way, and no passing over, under or ahead unless well clear."),
    E("no-collision-hazard-proximity", "Operation near other aircraft", "§ 107.37(b)", "assertion",
      "(b) No person may operate a small unmanned aircraft so close to another aircraft as to create a collision hazard.",
      note="Open degree 'so close' with its measure in the same constituent: 'as to create a collision hazard'. Not waivable per § 107.205 (outside extent)."),

    # § 107.39
    E("no-operation-over-human-beings", "Operation over human beings", "§ 107.39 introductory text", "operation",
      "No person may operate a small unmanned aircraft over a human being unless—",
      dependsOn=["over-human-direct-participant", "over-human-sheltered", "over-human-subpart-d"],
      note="Permitted if any one of (a), (b), (c) holds; otherwise prohibited. " + WAIVER_NOTE),
    E("over-human-direct-participant", "Exception: human being directly participating", "§ 107.39(a)", "operation",
      "(a) That human being is directly participating in the operation of the small unmanned aircraft;",
      clarity="ambiguous",
      ambiguity=gap("'Directly participating' is not defined in the slice or § 107.3 and no measure is stated."),
      note="Evaluated per human being overflown."),
    E("over-human-sheltered", "Exception: under a covered structure or inside a stationary vehicle", "§ 107.39(b)", "operation",
      "(b) That human being is located under a covered structure or inside a stationary vehicle that can provide reasonable protection from a falling small unmanned aircraft; or",
      dependsOn=["shelter-reasonable-protection"],
      note="Location (covered structure / stationary vehicle) is a parameter; adequacy is the assertion."),
    E("shelter-reasonable-protection", "Reasonable protection from a falling small unmanned aircraft", "§ 107.39(b)", "assertion",
      "that can provide reasonable protection from a falling small unmanned aircraft",
      note="Measure quoted: 'from a falling small unmanned aircraft'. Whether 'reasonable' attaches to structure and vehicle, or only the vehicle, is read here as both."),
    E("over-human-subpart-d", "Exception: subpart D operational category", "§ 107.39(c)", "operation",
      "(c) The operation meets the requirements of at least one of the operational categories specified in subpart D of this part.",
      crossReferences=[{"cites": "subpart D of this part", "unmapped": OUTSIDE}],
      note="Cannot be evaluated inside this extent; whether an operation meets a category is outside the slice."),

    # § 107.41
    E("controlled-airspace-authorization", "Operation in certain airspace", "§ 107.41", "operation",
      "No person may operate a small unmanned aircraft in Class B, Class C, or Class D airspace or within the lateral boundaries of the surface area of Class E airspace designated for an airport unless that person has prior authorization from Air Traffic Control (ATC).",
      note="Airspace class and ATC authorization are caller-supplied parameters (airspace designations come from outside the corpus). " + WAIVER_NOTE),

    # § 107.45
    E("prohibited-restricted-area-permission", "Operation in prohibited or restricted areas", "§ 107.45", "operation",
      "No person may operate a small unmanned aircraft in prohibited or restricted areas unless that person has permission from the using or controlling agency, as appropriate.",
      note="Area status and agency permission are parameters. Not waivable per § 107.205 (outside extent)."),

    # § 107.49
    E("preflight-assess-environment", "Preflight assessment of the operating environment", "§ 107.49 introductory text, (a), (a)(1), (a)(2), (a)(3), (a)(4)", "assertion",
      "Prior to flight, the remote pilot in command must: (a) Assess the operating environment, considering risks to persons and property in the immediate vicinity both on the surface and in the air. This assessment must include: (1) Local weather conditions; (2) Local airspace and any flight restrictions; (3) The location of persons and property on the surface; and (4) Other ground hazards.",
      note="Measure quoted: 'considering risks to persons and property in the immediate vicinity'; fixed content set (1)-(4). All four must be asserted."),
    E("preflight-brief-participants", "Preflight briefing of participants", "§ 107.49(b)", "assertion",
      "(b) Ensure that all persons directly participating in the small unmanned aircraft operation are informed about the operating conditions, emergency procedures, contingency procedures, roles and responsibilities, and potential hazards;",
      note="Fixed set of five matters, each open-textured; asserted per matter. Timing 'Prior to flight' is in the section introductory text, outside this span."),
    E("preflight-control-links", "Preflight check of control links", "§ 107.49(c)", "operation",
      "(c) Ensure that all control links between ground control station and the small unmanned aircraft are working properly;",
      clarity="ambiguous",
      ambiguity=gap("'Working properly' states no measure."),
      note="Timing from the section introductory text: prior to flight."),
    E("preflight-power", "Preflight check of available power", "§ 107.49(d)", "assertion",
      "(d) If the small unmanned aircraft is powered, ensure that there is enough available power for the small unmanned aircraft system to operate for the intended operational time;",
      note="Measure quoted: 'to operate for the intended operational time'. Whether the aircraft is powered is a parameter."),
    E("preflight-object-secure", "Preflight: attached or carried objects secure", "§ 107.49(e)", "operation",
      "(e) Ensure that any object attached or carried by the small unmanned aircraft is secure",
      clarity="ambiguous",
      ambiguity=gap("'Secure' carries no measure of its own; it may be read as measured by the following 'does not adversely affect' clause, but the text joins them with 'and' as separate conditions."),
      note="Split from preflight-object-no-adverse-effect because only that constituent states a measure."),
    E("preflight-object-no-adverse-effect", "Preflight: attached objects do not adversely affect flight", "§ 107.49(e)", "assertion",
      "does not adversely affect the flight characteristics or controllability of the aircraft",
      note="Measure quoted: 'flight characteristics or controllability of the aircraft'."),
    E("preflight-subpart-d-aircraft", "Preflight: aircraft meets subpart D requirements", "§ 107.49(f)", "operation",
      "(f) If the operation will be conducted over human beings under subpart D of this part, ensure that the aircraft meets the requirements of § 107.110, § 107.120(a), § 107.130(a), or § 107.140, as applicable.",
      enabledBy=["over-human-subpart-d"],
      crossReferences=[{"cites": "subpart D of this part", "unmapped": OUTSIDE},
                       {"cites": "§ 107.110", "unmapped": OUTSIDE},
                       {"cites": "§ 107.120(a)", "unmapped": OUTSIDE},
                       {"cites": "§ 107.130(a)", "unmapped": OUTSIDE},
                       {"cites": "§ 107.140", "unmapped": OUTSIDE}],
      note="Reachable only for an operation relying on the subpart D exception in § 107.39(c)."),

    # § 107.51
    E("operating-limitations-compliance", "Compliance with operating limitations", "§ 107.51 introductory text", "operation",
      "A remote pilot in command and the person manipulating the flight controls of the small unmanned aircraft system must comply with all of the following operating limitations when operating a small unmanned aircraft system:",
      dependsOn=["groundspeed-limit", "altitude-limit", "min-flight-visibility", "cloud-clearance"],
      note="Obligation falls on both named persons; all four limitations must hold. " + WAIVER_NOTE),
    E("groundspeed-limit", "Maximum groundspeed", "§ 107.51(a)", "value",
      "(a) The groundspeed of the small unmanned aircraft may not exceed 87 knots (100 miles per hour).",
      clarity="ambiguous",
      ambiguity=gap("The limit is stated in two units that are not equal: 87 knots is about 100.1 miles per hour, so a groundspeed between 100 mph and 87 knots exceeds one figure and not the other."),
      note="Test at exactly the limit (not exceeding) and just above in each unit."),
    E("max-altitude-agl", "Maximum altitude above ground level", "§ 107.51(b)", "value",
      "(b) The altitude of the small unmanned aircraft cannot be higher than 400 feet above ground level,",
      note="400 feet AGL, inclusive."),
    E("altitude-limit", "Altitude limitation and structure exception", "§ 107.51(b), (b)(1), (b)(2)", "operation",
      "(b) The altitude of the small unmanned aircraft cannot be higher than 400 feet above ground level, unless the small unmanned aircraft: (1) Is flown within a 400-foot radius of a structure; and (2) Does not fly higher than 400 feet above the structure's immediate uppermost limit.",
      dependsOn=["max-altitude-agl", "structure-radius", "structure-altitude-allowance"],
      note="Both exception limbs must hold. Test: above 400 AGL outside radius (violation), inside radius under structure top + 400 (allowed), inside radius above structure top + 400 (violation)."),
    E("structure-radius", "Structure exception radius", "§ 107.51(b)(1)", "value",
      "(1) Is flown within a 400-foot radius of a structure; and"),
    E("structure-altitude-allowance", "Height allowed above a structure", "§ 107.51(b)(2)", "value",
      "(2) Does not fly higher than 400 feet above the structure's immediate uppermost limit."),
    E("min-flight-visibility", "Minimum flight visibility", "§ 107.51(c)", "value",
      "(c) The minimum flight visibility, as observed from the location of the control station must be no less than 3 statute miles.",
      dependsOn=["flight-visibility-definition"],
      note="3 statute miles inclusive, observed from the control station ('control station' defined in § 107.3). Observed visibility is a parameter."),
    E("flight-visibility-definition", "Flight visibility defined", "§ 107.51(c)", "value",
      "For purposes of this section, flight visibility means the average slant distance from the control station at which prominent unlighted objects may be seen and identified by day and prominent lighted objects may be seen and identified by night.",
      note="Definition; the measured distance is a parameter. 'By night' uses 'night', not defined in the slice."),
    E("cloud-clearance", "Minimum distance from clouds", "§ 107.51(d), (d)(1), (d)(2)", "operation",
      "(d) The minimum distance of the small unmanned aircraft from clouds must be no less than: (1) 500 feet below the cloud; and (2) 2,000 feet horizontally from the cloud.",
      clarity="ambiguous",
      dependsOn=["cloud-clearance-below", "cloud-clearance-horizontal"],
      ambiguity=gap("Read literally, 'and' requires the aircraft to be both at least 500 feet below and at least 2,000 feet horizontally from the cloud, which would bar flight above or level with a distant cloud; the corpus does not say whether the two distances apply jointly, alternatively, or by relative position, nor states any clearance above a cloud."),
      note="Test must cover positions below, beside and above a cloud."),
    E("cloud-clearance-below", "Vertical clearance below cloud", "§ 107.51(d)(1)", "value",
      "(1) 500 feet below the cloud; and"),
    E("cloud-clearance-horizontal", "Horizontal clearance from cloud", "§ 107.51(d)(2)", "value",
      "(2) 2,000 feet horizontally from the cloud."),
]

SECTIONS = ["107.25", "107.29", "107.31", "107.33", "107.35", "107.36", "107.37", "107.39",
            "107.41", "107.45", "107.49", "107.51"]

doc = {
    "schemaVersion": 1,
    "corpus": SRC,
    "baseline": {"contentHash": "80f6bc4b002df9dcc60a651fec30a2dc3590081cc3e5fd431d9885c69b7ce35e",
                 "hashDerivation": "ecfr-versioner-xml"},
    "extent": {"unit": "section-designation", "sections": ["§ " + s for s in SECTIONS]},
    "manifest": {
        "schemaVersion": 1,
        "corpora": [{"sourceId": SRC, "title": "Title 14, Code of Federal Regulations, Part 107",
                     "adapter": "ecfr-xml", "locatorGrammar": "section-designation",
                     "contentHash": "80f6bc4b002df9dcc60a651fec30a2dc3590081cc3e5fd431d9885c69b7ce35e",
                     "hashDerivation": "ecfr-versioner-xml", "asOf": "2026-01-01",
                     "boundaryPolicy": "pin-in-repo", "licence": "public-domain",
                     "verification": "committed-copy", "committedPath": "part107.xml",
                     "quotation": "verbatim"}],
        "references": [
            {"sourceId": "cfr-14-1.1", "citation": "14 CFR 1.1", "admitted": False},
            {"sourceId": "cfr-49-171.8", "citation": "49 CFR 171.8", "admitted": False},
            {"sourceId": "air-almanac", "citation": "Air Almanac", "admitted": False},
        ],
    },
    "entries": entries,
}

out = os.path.join(HERE, "blind-map.json")
with open(out, "w") as f:
    json.dump(doc, f, indent=2, ensure_ascii=False)
    f.write("\n")


# ---------------- verification ----------------
def norm(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s))).strip()


def paragraphs():
    xml = open(os.path.join(HERE, "part107-slice.xml"), encoding="utf-8").read()
    idx = {}
    for m in re.finditer(r'<DIV8 N="([\d.]+)" TYPE="SECTION".*?</DIV8>', xml, re.S):
        sec, body = m.group(1), m.group(0)
        l1 = None
        for p in re.findall(r"<P>(.*?)</P>", body, re.S):
            t = norm(p)
            lm = re.match(r"\((\w+)\)", t)
            if not lm:
                key = sec
            elif lm.group(1).isdigit():
                key = f"{sec}({l1})({lm.group(1)})"
            else:
                l1 = lm.group(1)
                key = f"{sec}({l1})"
            idx[key] = idx.get(key, "") + (" " if key in idx else "") + t
    return idx


def resolve(citation, idx):
    parts = [p.strip() for p in citation.split(",")]
    m = re.match(r"§ ([\d.]+)(.*)$", parts[0])
    sec = m.group(1)
    keys = []
    for i, p in enumerate(parts):
        rest = m.group(2).strip() if i == 0 else p
        if rest in ("", "introductory text"):
            keys.append(sec)
        else:
            keys.append(sec + rest)
    return keys


def verify(doc):
    idx = paragraphs()
    ids = {e["id"] for e in doc["entries"]}
    refs = {r["sourceId"] for r in doc["manifest"]["references"]}
    errs = []
    if len(ids) != len(doc["entries"]):
        errs.append("duplicate ids")
    for e in doc["entries"]:
        keys = resolve(e["locator"]["citation"], idx)
        missing = [k for k in keys if k not in idx]
        if missing:
            errs.append(f"{e['id']}: citation paragraphs not found {missing}")
            continue
        text = " ".join(idx[k] for k in keys)
        if norm(e["evidence"]) not in text:
            errs.append(f"{e['id']}: evidence not verbatim in {keys}")
        for f in ("dependsOn", "enabledBy", "suspendedBy"):
            for d in e.get(f, []):
                if d not in ids:
                    errs.append(f"{e['id']}: {f} unknown id {d}")
        for x in e.get("crossReferences", []):
            if x["cites"] not in e["evidence"]:
                errs.append(f"{e['id']}: cites not in evidence: {x['cites']}")
            if ("resolvedBy" in x) == ("unmapped" in x):
                errs.append(f"{e['id']}: crossReference must have exactly one of resolvedBy/unmapped")
            if "resolvedBy" in x and x["resolvedBy"] not in ids:
                errs.append(f"{e['id']}: resolvedBy unknown id {x['resolvedBy']}")
        if "definedElsewhere" in e and e["definedElsewhere"]["reference"] not in refs:
            errs.append(f"{e['id']}: definedElsewhere reference unknown")
        if "definedElsewhere" in e and "ambiguity" in e:
            errs.append(f"{e['id']}: definedElsewhere with ambiguity")
        if (e["clarity"] == "ambiguous") != ("ambiguity" in e):
            errs.append(f"{e['id']}: clarity/ambiguity mismatch")
    cited_secs = {resolve(e["locator"]["citation"], idx)[0].split("(")[0] for e in doc["entries"]}
    for s in SECTIONS:
        if s not in cited_secs:
            errs.append(f"extent section {s} not cited by any entry")
    return errs


json.load(open(out))  # parses
errors = verify(doc)
print(f"{len(entries)} entries written to {out}")
if errors:
    print("FAIL"); print("\n".join(errors)); sys.exit(1)
print("CHECK OK")
