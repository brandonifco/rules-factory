"""What a `status` claims. `implemented` carries its revision and the tests that prove it (#2);
an absent rule (0009) is `declined`, and nothing orders or gates on it.
"""
from .diagnostics import skip, verdict
from mapcontract.vocabulary import ID_LIST_FIELDS
from mapcontract.entry import entries_of, label


def tests_problems(name, tests):
    """What is wrong with a `tests` list, as report lines. Empty when it is well-formed."""
    if not isinstance(tests, list):
        return [f"  X  {name}: `tests` is not a list"]
    bad, seen = [], set()
    for position, item in enumerate(tests):
        if not isinstance(item, dict):
            bad.append(f"  X  {name}: tests[{position}] is not an object naming a test and its mutation")
            continue
        test, mutation = item.get("test"), item.get("mutation")
        if not isinstance(test, str) or not test.strip():
            bad.append(f"  X  {name}: tests[{position}] names no `test`")
        elif test in seen:
            bad.append(f"  X  {name}: names test {test!r} twice")
        else:
            seen.add(test)
        if not isinstance(mutation, str) or not mutation.strip():
            bad.append(f"  X  {name}: tests[{position}] ({test!r}) records no `mutation`; a test "
                       f"nobody has seen go red is not evidence")
    return bad


def check_status(ctx):
    """`implemented` is a claim with its evidence attached (#2), not a word someone typed.

    Two rules:

      * `implementedIn` is set when status becomes `implemented`, and only then;
      * an `implemented` entry names the tests that prove it in `tests`, non-empty, and every
        test carries the `mutation` that was recorded turning it red. Without them the entry is
        `mapped`, whatever the repository contains. Wherever `tests` appears, its shape is held
        to the same rule.

    What it cannot do: this file never sees an engine, so a named test that does not exist, or
    exists and never ran, passes here. That is the engine gate's check. And a recorded mutation
    proves one way of breaking the rule is caught, not that the test is good.
    """
    bad, implemented = [], 0
    for position, entry in enumerate(entries_of(ctx["map"])):
        if not isinstance(entry, dict):
            continue
        name = label(entry, position)
        if "tests" in entry:
            bad.extend(tests_problems(name, entry["tests"]))
        if entry.get("status") == "implemented":
            implemented += 1
            if not entry.get("implementedIn"):
                bad.append(f"  X  {name}: status is `implemented` but no `implementedIn` names the ruleset revision")
            if not entry.get("tests"):
                bad.append(f"  X  {name}: status is `implemented` but `tests` names no test that proves "
                           f"it; without one the entry is `mapped`")
        elif entry.get("implementedIn"):
            bad.append(f"  X  {name}: carries `implementedIn` while status is {entry.get('status')!r}")
    carriers = sum(1 for e in entries_of(ctx["map"])
                   if isinstance(e, dict) and (e.get("implementedIn") or "tests" in e))
    if not bad and not implemented and not carriers:
        return skip("no entry is `implemented` and none carries `implementedIn` or `tests`, so the "
                    "rules that accompany an implemented claim were not exercised", had_subject=False)
    return verdict(bad, f"{implemented} implemented entries all name their revision and the tests, "
                        f"each with a recorded mutation, that prove them",
                   "an implemented claim is missing its revision or its tests")


def check_absent(ctx):
    """`absentFrom` says the corpus does not contain the rule at all (0009).

    Three states share one schema and two of them are `scope: out`: read-and-declined, and
    read-and-not-there. `absentFrom` is the discriminator, and everything here follows from
    what it asserts:

      * it is a verdict, so `scope: out` and `status: declined` -- row 1 of the
        correspondence table dominates, and 0008's procedure has `scope: in` as its
        precondition, so an absent rule must never reach the gates;
      * a rule cannot be both nowhere in the corpus and somewhere in it the reader cannot
        reach, so `beyondAdapter` and `definedElsewhere` are excluded;
      * an absent rule has no words, so it cannot be ambiguous about them;
      * nothing can be implemented after a rule that does not exist, so an absent entry
        neither depends on nor gates anything, and nothing names it in either relation.
        That edge would be unsatisfiable forever, which is what `blocked` looks like when
        it will never clear.

    What it cannot do: this file never reads a corpus, so the claim itself -- *the words
    are not there* -- is not tested here. `check-locators.py` searches the text for the
    terms `searched` names and fails when one of them turns up.
    """
    bad, carriers, absent_ids = [], [], set()
    for position, entry in enumerate(entries_of(ctx["map"])):
        if not isinstance(entry, dict):
            continue
        name = label(entry, position)
        if "absentFrom" not in entry:
            continue
        carriers.append(name)
        if isinstance(entry.get("id"), str):
            absent_ids.add(entry["id"])
        if not isinstance(entry.get("absentFrom"), dict):
            bad.append(f"  X  {name}: `absentFrom` is not an object")
            continue
        if entry.get("scope") != "out":
            bad.append(f"  X  {name}: carries `absentFrom` while scope is "
                       f"{entry.get('scope')!r}; a rule the corpus does not state is not one "
                       f"the engine covers, and row 1 must dominate")
        if entry.get("status") != "declined":
            bad.append(f"  X  {name}: carries `absentFrom` while status is "
                       f"{entry.get('status')!r}; there is no rule to have built")
        for field in ("beyondAdapter", "definedElsewhere"):
            if field in entry:
                bad.append(f"  X  {name}: carries `absentFrom` and `{field}`; the rule is either "
                           f"nowhere in this corpus or somewhere in it we cannot reach, not both")
        if "ambiguity" in entry:
            bad.append(f"  X  {name}: carries `absentFrom` and an `ambiguity` block; an absent "
                       f"rule has no words to be ambiguous about")
        for field in ID_LIST_FIELDS:
            if entry.get(field):
                bad.append(f"  X  {name}: carries `absentFrom` and a non-empty `{field}`; a rule "
                           f"the corpus does not state orders nothing and gates nothing")

    for position, entry in enumerate(entries_of(ctx["map"])):
        if not isinstance(entry, dict):
            continue
        name = label(entry, position)
        for field in ID_LIST_FIELDS:
            for ref in entry.get(field) or []:
                if isinstance(ref, str) and ref in absent_ids:
                    bad.append(f"  X  {name}: {field} names {ref!r}, which carries `absentFrom`; "
                               f"that edge can never be satisfied")
    if not carriers:
        return skip("no entry carries `absentFrom`, so the rules about an absent rule are "
                    "vacuous over this map", had_subject=False)
    return verdict(bad, f"{len(carriers)} absent-rule entr{'y' if len(carriers) == 1 else 'ies'} "
                        f"({', '.join(sorted(carriers))}): out, declined, carrying nothing that "
                        f"contradicts an absence, and depended on by nothing",
                   "an absent-rule entry claims something else as well")
