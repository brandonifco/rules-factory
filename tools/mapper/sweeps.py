"""The completeness challenge, as code the mapper runs (#250).

`requiredSweeps` named eleven challenges and nothing ran any of them, so `mapper protocol` said
`NOT RUN` on every invocation to keep the declaration from reading as coverage. This is what
makes that line stop being true.

## The question a sweep asks, and why it is not #208 again

A sweep is **not** a scan of the corpus for cue phrases. That shape was measured and found
structurally blind: against a corpus that points by naming its defined terms, the phrase list
detected 0 pointers in passages holding 51 references
([#208](https://github.com/brandonifco/rules-factory/issues/208)). Rebuilding it over the whole
corpus would produce thousands of hits nobody can act on, and a cue it missed would be invisible.

The candidate set is what changed. `inventory.py` sorts every unit in a declared extent into
**reached**, **rejected** and **unaccounted**, and the six committed maps report 540 unaccounted
units of 806 ([#267](https://github.com/brandonifco/rules-factory/issues/267)). A sweep runs over
that pile alone, and asks:

> Is there an **unaccounted** unit that looks like it states a rule of this kind, and no entry
> quotes it?

That makes each sweep a **recall device over a bounded candidate set**, and it changes the risk
profile completely. A cue this misses does not hide the unit: the inventory still reports it as
unaccounted, because a unit is unaccounted until a quote reaches it or a rejection records it.
The cues sort a pile that is already visible; they are not what makes it visible. The denominator
is the difference, and it is why the same mechanism that failed as a detector works here.

A finding is never a failure of the map. Whether an unaccounted unit owed an entry is decided by
reading the corpus, which this tool does not do, so findings are **NOT VERIFIED** (exit 3), the
verdict the inventory already gives the same units.

## Cues, and the silent zero

Each sweep carries a built-in default cue list, and a corpus may add its own in the protocol's
optional `sweepCues`, in the shape `pointerPhrases` already uses (0026): a literal phrase or
`{"regex": "..."}`, matched case-insensitively. Declared cues are read **in addition to** the
built-in list, for the same reason 0026 gives -- a universal list either fires on words that are
not cues in some corpus or misses the ones that are.

A sweep that is declared, has candidates to examine, and fires on **none** of them fails
(exit 1). It has either the wrong cues for this corpus or genuinely nothing to say, and those two
must be distinguishable: a corpus where the second is true declares `sweepCuesReason` for that
sweep, and the reason is refused for a sweep that did fire. That is 0026's rule for
`pointerPhrases` / `pointerPhrasesReason`, applied to the same shape of claim.

## `extent-coverage` and `cross-references` are not implemented twice

**`extent-coverage`** delegates to `inventory.py`. It is the one sweep whose candidate set is the
whole extent rather than the unaccounted pile, because its yield *is* the unaccounted pile -- it
is the denominator every other sweep is measured against. The name is kept rather than retired
because a protocol has to be able to say that this mapping owes a coverage challenge, and
`mapper inventory` is a separate command that `requiredSweeps` cannot oblige. Nothing is measured
twice: `run()` takes the `Inventory` the caller already computed and reports it.

It is also the one sweep exempt from the silent-zero rule. Zero yield there means every unit of
the extent is reached or recorded -- the outcome the inventory exists to reward -- not a cue list
that saw nothing.

**`cross-references`** keeps its name for the complementary reason. `mapper pointers` implements
the `defined-term-use` mechanism and `check-map.py --only cross-references` implements the
`phrase` mechanism, and both read **entries' quoted evidence**: they ask whether a pointer the
map already quotes is declared. Neither can see a pointer in a passage no entry quotes, which is
precisely the unaccounted pile. So this sweep asks the other half of the question, over units
those two cannot reach. It re-implements neither detector: its corpus-specific cues are read from
the manifest's own `pointerPhrases`, the declaration 0026 already requires, so the words are
declared once and read from the one place that holds them.
"""
import re

from mapper import inventory as inventory_step
from mapper.protocol import Refused

#: How many findings a sweep prints before it says how many more there are. A sweep that prints
#: four hundred lines has sorted nothing.
SHOWN = 3


def compile_cue(item, where):
    """One cue, as a compiled pattern: a literal phrase or `{"regex": "..."}` (0026's shape).

    A literal matches across any run of whitespace and on word boundaries where its edges are
    alphanumeric, so a cue does not fire inside a longer word. Units arrive whitespace-normalised
    from `corpus.py`, so the flexibility costs nothing and survives a corpus that is not.
    """
    if isinstance(item, dict):
        pattern = item.get("regex")
        if not isinstance(pattern, str) or not pattern:
            raise Refused(f"{where}: a cue object names no `regex`")
        try:
            compiled = re.compile(pattern, re.I)
        except re.error as error:
            raise Refused(f"{where}: regex {pattern!r} does not compile: {error}")
        if compiled.match(""):
            raise Refused(f"{where}: regex {pattern!r} matches the empty string, so it would fire "
                          f"on every unit and sort nothing")
        return compiled
    if isinstance(item, str) and item.strip():
        body = r"\s+".join(re.escape(word) for word in item.split())
        edge = r"\b" if item.strip()[0].isalnum() else ""
        tail = r"\b" if item.strip()[-1].isalnum() else ""
        return re.compile(edge + body + tail, re.I)
    raise Refused(f"{where}: cue {item!r} is neither a phrase nor a regex object")


class Finding:
    """One unaccounted unit a sweep fired on, and the cues that fired."""

    def __init__(self, unit, cues):
        self.unit = unit
        self.cues = cues

    def __repr__(self):
        return f"Finding({self.unit.key!r}, {self.cues!r})"


class Result:
    """What one sweep did on one map: what it looked at, and what it found."""

    def __init__(self, name, question, candidates, findings, implemented=True, reason=None,
                 live=0):
        self.name = name
        self.question = question
        self.candidates = candidates      # how many units it examined
        self.findings = findings          # list of Finding
        self.implemented = implemented
        self.reason = reason              # the declared account of a zero yield, when there is one
        self.live = live                  # accounted units of this kind the cues also fire on

    @property
    def silent(self):
        """Declared, implemented, had something to examine, and fired on nothing anywhere.

        `live` is what makes the two halves of a zero distinguishable **from the corpus** rather
        than from the mapper's word. A sweep that fires on no unaccounted unit but fires on units
        the walk *reached* has cues that work in this corpus and a walk that reached every unit of
        that kind -- the outcome a completeness challenge is asking for, and not a silent zero. A
        sweep that fires nowhere in the extent at all is the ambiguous case, and that one needs a
        declared reason.
        """
        return self.implemented and self.candidates and not self.findings and not self.live


class Sweep:
    """One named completeness challenge.

    `name` is a value of `protocol.SWEEPS`; `question` is what it asks, printed on every run so
    a reader does not have to infer it from the name.
    """

    exempt_from_silent_zero = False

    def __init__(self, name, question):
        self.name = name
        self.question = question

    def run(self, units, taken, cues):
        raise NotImplementedError


class CueSweep(Sweep):
    """A recall device over the unaccounted pile: which of these units look like this kind of rule.

    `kinds` is a set of unit kinds that fire on their own, regardless of cue. The two grammars
    that can tell a worked example or a table from a paragraph say so in `Unit.kind`, and a
    sweep for examples should not have to guess from words what the corpus's own structure
    already states.
    """

    def __init__(self, name, question, cues=(), kinds=()):
        Sweep.__init__(self, name, question)
        self.cues = tuple(cues)
        self.kinds = frozenset(kinds)

    def compiled(self, extra):
        built_in = [compile_cue(cue, f"{self.name} built-in cue") for cue in self.cues]
        return built_in + [compile_cue(cue, f"sweepCues[{self.name!r}][{position}]")
                           for position, cue in enumerate(extra)]

    def fired(self, unit, patterns):
        """Which cues fire on this unit, as their patterns, sorted so a report is stable."""
        return sorted({pattern.pattern for pattern in patterns if pattern.search(unit.text)})

    def run(self, units, taken, cues):
        patterns = self.compiled(cues)
        candidates = taken.unaccounted
        unaccounted = {unit.key for unit in candidates}
        findings, live = [], 0
        for unit in units:
            fired = self.fired(unit, patterns)
            if unit.kind in self.kinds:
                fired = [f"kind={unit.kind}"] + fired
            if not fired:
                continue
            if unit.key in unaccounted:
                findings.append(Finding(unit, fired))
            else:
                live += 1
        return Result(self.name, self.question, len(candidates), findings, live=live)


class CrossReferenceSweep(CueSweep):
    """The cross-reference sweep, which does not count a unit naming its own section.

    A designation cue fires on every heading of a designated corpus -- `§ 107.25 Operation from a
    moving vehicle or aircraft.` names § 107.25 -- and a passage naming the section it is in
    points nowhere. 0009 already refuses a self-reference as a pointer, and without this the sweep
    would fire on 12 of Part 107's 12 unaccounted units and have sorted nothing.

    The unit's own designation comes from its **key**, which the adapter built from the corpus's
    own hierarchy, so nothing here parses a citation. A grammar whose keys carry no designation --
    a page-marked text -- has no self-reference to drop and is unaffected.
    """

    OWN = re.compile(r"^(§+\s*[\w.-]+)")

    def fired(self, unit, patterns):
        own = self.OWN.match(unit.key)
        if own is None:
            return CueSweep.fired(self, unit, patterns)
        designation = re.compile(r"\s+".join(re.escape(word) for word in own.group(1).split()),
                                 re.I)
        self_spans = [(m.start(), m.end()) for m in designation.finditer(unit.text)]
        found = set()
        for pattern in patterns:
            for match in pattern.finditer(unit.text):
                if any(lo <= match.start() and match.end() <= hi for lo, hi in self_spans):
                    continue
                found.add(pattern.pattern)
                break
        return sorted(found)


class ExtentCoverage(Sweep):
    """The coverage challenge, delegated to the inventory rather than measured a second time."""

    exempt_from_silent_zero = True

    def __init__(self):
        Sweep.__init__(self, "extent-coverage",
                       "is there a unit inside the declared extent that no entry's quote reaches "
                       "and no rejection records?")

    def run(self, units, taken, cues):
        if cues:
            raise Refused("sweepCues['extent-coverage'] declares cues, and this sweep reads none: "
                          "it delegates to `mapper inventory`, whose candidate set is the whole "
                          "extent and whose yield is the unaccounted pile")
        return Result(self.name, self.question, len(units),
                      [Finding(unit, ["unaccounted"]) for unit in taken.unaccounted])


# The built-in cue lists. Each is the shape the challenge takes in the corpora this repository
# holds -- a regulation, a statute's regulations, a printed rulebook, a game's reference document
# -- and each is meant to be added to by the corpus that knows its own words. Where a cue would
# fire on the negative of what it asks (a permission's `may` inside a prohibition's `may not`),
# the exclusion is in the pattern rather than left to the reader of the output.
REGISTRY = {}


def _register(sweep):
    REGISTRY[sweep.name] = sweep
    return sweep


_register(CueSweep(
    "definitions",
    "is there an unaccounted unit that defines a term, which no entry quotes?",
    cues=[{"regex": r"(?<!by\s)\bmeans\b(?!\s+of\b)"}, "is defined as", "are defined as",
          "shall mean", "has the meaning", "refers to", "the term", "as used in this",
          "for purposes of this", "for the purposes of this"]))

_register(CueSweep(
    "vocabulary",
    "is there an unaccounted unit that names a thing the corpus's rules then use, which no entry "
    "quotes?",
    cues=["is called", "are called", "called the", "is known as", "are known as", "known as",
          "is termed", "are termed", "termed", "is designated", "designated as", "so-called"]))

_register(CueSweep(
    "applicability",
    "is there an unaccounted unit that says what the rules apply to, which no entry quotes?",
    cues=["applies to", "apply to", "applies only", "does not apply", "do not apply",
          "shall apply", "is applicable", "are applicable", "in the case of", "with respect to",
          "this part", "this section", "this subpart"]))

_register(CueSweep(
    "exceptions",
    "is there an unaccounted unit that carves an exception out of a rule, which no entry quotes?",
    cues=["except", "unless", "other than", "notwithstanding", "provided that", "but not",
          "does not apply", "do not apply", "shall not apply", "is exempt", "are exempt"]))

_register(CueSweep(
    "permissions",
    "is there an unaccounted unit that permits something, which no entry quotes?",
    cues=[{"regex": r"\bmay\b(?!\s+not\b)"}, "is permitted", "are permitted", "is allowed",
          "are allowed", "at the option of", "may elect", "is entitled"]))

_register(CueSweep(
    "prohibitions",
    "is there an unaccounted unit that forbids something, which no entry quotes?",
    cues=["may not", "must not", "shall not", "no person may", "is prohibited", "are prohibited",
          "is not permitted", "are not permitted", "cannot", "never"]))

_register(CueSweep(
    "undefined-terms",
    "is there an unaccounted unit that turns on a term of degree the corpus states no measure "
    "for?",
    # The sweep docs/method.md calls trial 1's: the field nothing compares against the corpus is
    # `clarity`, and a rule whose operative word is `reasonable` or `sufficient` is the one most
    # often called clear. "well clear" appears once in Part 107 and is the measure of a
    # prohibition (method.md).
    cues=["reasonable", "reasonably", "sufficient", "sufficiently", "adequate", "appropriate",
          "practicable", "promptly", "substantially", "undue", "excessive", "satisfactory",
          "suitable", "as necessary", "well clear"]))

_register(CueSweep(
    "examples",
    "is there an unaccounted worked example, which no entry quotes and no rejection records?",
    # 0031: an example is sometimes the corpus's only authority for a rule, and sometimes a bound
    # on a term an operative rule leaves open. Both are decisions a mapper makes per example, and
    # an example nobody recorded is an example nobody made either decision about.
    cues=["for example", "for instance", "such as", "e.g.", "illustrat", "assume the same facts",
          {"regex": r"^\(?Example\b"}],
    kinds=("worked-example",)))

_register(CueSweep(
    "tables",
    "is there an unaccounted table, which no entry quotes and no rejection records?",
    cues=["the following table", "the table below", "shown on the", {"regex": r"\bTable\b"},
          "in the columns", "in the column"],
    kinds=("table",)))

_register(CrossReferenceSweep(
    "cross-references",
    "is there an unaccounted unit that points at a meaning given elsewhere, which no entry "
    "quotes?",
    # The built-in half of 0026's list. The corpus's own `pointerPhrases` are added to it by
    # `cues_for`, read from the manifest rather than copied here: 0026 already requires that
    # declaration, and a second copy would be a second definition to keep in step.
    cues=["see", "as provided in", "as described in", "as defined in", "pursuant to",
          "in accordance with", "subject to", "under paragraph", "of this section",
          "of this part", "of this chapter", {"regex": r"§+\s*\d"}]))

_register(ExtentCoverage())


def cues_for(name, protocol, corpus):
    """The corpus's declared cues for one sweep, added to that sweep's built-in list.

    `cross-references` also reads the manifest corpus's `pointerPhrases` (0026). Those are the
    words this corpus points with, declared once for the detector that reads entries; a sweep
    over the units no entry reaches asks the same question of the same words, and reading them
    from the manifest is what keeps the two from drifting.
    """
    declared = protocol.get("sweepCues") if isinstance(protocol, dict) else None
    extra = list((declared or {}).get(name) or []) if isinstance(declared, dict) else []
    if name == "cross-references" and isinstance(corpus, dict):
        phrases = corpus.get("pointerPhrases")
        if isinstance(phrases, list):
            extra += phrases
    return extra


def reason_for(name, protocol):
    declared = protocol.get("sweepCuesReason") if isinstance(protocol, dict) else None
    value = (declared or {}).get(name) if isinstance(declared, dict) else None
    return value if isinstance(value, str) and value.strip() else None


def run(protocol, units, taken, corpus=None):
    """Every sweep the protocol requires, in the order it declares them.

    A sweep this mapper cannot run is a `Result` with `implemented=False`, never a skipped one.
    That is the standing rule here and the reason `requiredSweeps` was allowed to exist before
    any sweep did: a declared interrogation nobody performs reads as coverage.
    """
    results = []
    for name in protocol.get("requiredSweeps") or []:
        sweep = REGISTRY.get(name)
        if sweep is None:
            results.append(Result(name, "not asked: no sweep of this name is implemented", 0, [],
                                  implemented=False))
            continue
        result = sweep.run(units, taken, cues_for(name, protocol, corpus))
        result.reason = reason_for(name, protocol)
        results.append(result)
    return results


def problems(results):
    """The lines that make a run fail: a silent zero, and a reason for a sweep that fired."""
    found = []
    for result in results:
        sweep = REGISTRY.get(result.name)
        exempt = sweep is not None and sweep.exempt_from_silent_zero
        if result.silent and not exempt and not result.reason:
            found.append(f"  X  {result.name}: examined {result.candidates} unaccounted unit(s) "
                         f"and fired on none, and fired on no accounted unit of the extent "
                         f"either. Either the cues are wrong for this corpus or it states nothing "
                         f"of this kind, and the two are not the same: add cues this corpus uses "
                         f"in sweepCues[{result.name!r}], or declare "
                         f"sweepCuesReason[{result.name!r}] (0026)")
        if result.reason and (result.findings or result.live):
            found.append(f"  X  {result.name}: sweepCuesReason says this corpus states nothing of "
                         f"this kind, and the sweep fired on {len(result.findings)} unaccounted "
                         f"and {result.live} accounted unit(s); a reason beside a live cue is a "
                         f"stale claim")
    return found


def lines(results, show_all=False):
    """The report. Counts first, then a bounded sample of what each sweep found."""
    out = []
    for result in results:
        if not result.implemented:
            out.append(f"  NOT IMPLEMENTED  {result.name}: this protocol requires it and no sweep "
                       f"of that name is in the registry")
            continue
        out.append(f"  {result.name}: {len(result.findings)} finding(s) in "
                   f"{result.candidates} candidate unit(s)"
                   + (f", and {result.live} accounted unit(s) of this kind the walk reached"
                      if result.live else "")
                   + f" -- {result.question}")
        if result.reason and not result.findings:
            out.append(f"     reason declared: {result.reason}")
        shown = result.findings if show_all else result.findings[:SHOWN]
        for finding in shown:
            out.append(f"  ?  {finding.unit.key} [{finding.unit.kind}] "
                       f"({', '.join(finding.cues)}): {finding.unit.text[:80]}"
                       + ("..." if len(finding.unit.text) > 80 else ""))
        if len(shown) < len(result.findings):
            out.append(f"  ?  ... and {len(result.findings) - len(shown)} more; --list prints "
                       f"every one")
    return out


def unimplemented(results):
    return [result.name for result in results if not result.implemented]


def total_findings(results):
    return sum(len(result.findings) for result in results)


def take(units, document, rejected):
    """The inventory this run is measured against -- one measurement, shared by every sweep."""
    return inventory_step.take(units, document, rejected)
