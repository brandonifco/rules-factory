"""What kind of review a change owes, named once from the diff (decision 0076, #595).

Until this, three rails each asked one question of a pull request's changed paths -- "is any of
them on `review.semanticPaths`?" -- and a yes meant the same ceremony every time: a named entry, a
committed adversarial self-review of it, a semantic packet, and a recorded semantic verdict. The
question was too coarse. `docs/decisions/**` is on that list by default, so a pull request that
adds one decision record and nothing else had to invent a principal entry and answer twenty classes
of attack "not applicable" about code it did not write; and a factory update, which writes the
generated files and the pins, had to be read as a rule by a reviewer who could not read it as one.

This module is the one statement of the answer, vendored into every engine as
`scripts/factory/reviewclass.py` so `tools/pr-policy.py`, `tools/conformance-gate.py` and
`tools/review-packet.py` cannot come to disagree about it. Five classes:

  * `semantic-implementation` -- executable semantics: handlers, legality, state, outcomes, the
    overlay, the corpus, anything under the semantic surface this module cannot show is inert.
    Names its entries, has an entry-scoped self-review, a semantic packet and a verdict.
  * `semantic-ruling` -- an authoritative decision that changes how rules are read: an existing
    decision record edited or withdrawn, or one that says it supersedes another. Names its entries
    or its decision scope, has a decision-scoped review record, a semantic packet and a verdict.
  * `decision-record-only` -- a new decision record that overrules nothing. Records what was
    decided; the work that builds to it is its own pull request and is reviewed as one.
  * `generated-or-provenance` -- the factory's own writing, with the map, the corpora and the
    randomness provably unmoved. Structural and provenance validation, no semantic verdict.
  * `documentation` -- a document, a comment, a process file: no executable effect.

**The diff decides; the pull request's words can only add review.** The class is computed here
from the changed paths and what changed in them. A pull request's `review class:` line is a claim
checked against it, and it can do exactly two things: opt in to an exemption the diff already
shows, and raise a computed class to a stronger one. It can never lower a class the diff
computed, and a diff that touches the semantic surface and says nothing is reviewed as an
implementation, as every such diff was before this existed. **An exemption must be claimed.**

**It fails closed.** Anything this module cannot prove inert is `semantic-implementation`: a path
it cannot classify, a file it cannot read, a lexer that cannot tell where a comment ends, a
provenance record it cannot compare, a factory update that moved the map. Each exemption below
is a closed predicate and not a judgement, and none is wider than the one fact it rests on.

Everything is a function of its arguments: the caller reads the bytes and hands them in. Standard
library only, plus `reviewscope` for the C# lexer it already owns.
"""
import hashlib
import json
import re

import reviewscope

SEMANTIC_IMPLEMENTATION = "semantic-implementation"
SEMANTIC_RULING = "semantic-ruling"
DECISION_RECORD_ONLY = "decision-record-only"
GENERATED_OR_PROVENANCE = "generated-or-provenance"
DOCUMENTATION = "documentation"
CLASSES = (SEMANTIC_IMPLEMENTATION, SEMANTIC_RULING, DECISION_RECORD_ONLY, GENERATED_OR_PROVENANCE, DOCUMENTATION)
SEMANTIC = frozenset({SEMANTIC_IMPLEMENTATION, SEMANTIC_RULING})
#: Which of two semantic classes is the stronger. A declaration may raise a class and never lower one.
RANK = {SEMANTIC_IMPLEMENTATION: 2, SEMANTIC_RULING: 1}
#: Which of the non-semantic classes a mixed diff is *named* as: the most specific description of
#: what it holds. It decides a label and nothing else; none of them owes a semantic review.
SPECIFICITY = (GENERATED_OR_PROVENANCE, DECISION_RECORD_ONLY, DOCUMENTATION)

#: What each class owes. The one table every rail reads, so "owes a verdict" has one source.
OWES = {
    SEMANTIC_IMPLEMENTATION: {"entries": True, "self_review": True, "ruling_review": False,
                              "packet": True, "verdict": True},
    SEMANTIC_RULING: {"entries": False, "self_review": False, "ruling_review": True,
                      "packet": True, "verdict": True},
    DECISION_RECORD_ONLY: {"entries": False, "self_review": False, "ruling_review": False,
                           "packet": False, "verdict": False},
    GENERATED_OR_PROVENANCE: {"entries": False, "self_review": False, "ruling_review": False,
                              "packet": False, "verdict": False},
    DOCUMENTATION: {"entries": False, "self_review": False, "ruling_review": False,
                    "packet": False, "verdict": False},
}

REMOVALS = frozenset({"DELETED", "REMOVED"})
DERIVED = "derived"
DECISION_RECORD = re.compile(r"\Adocs/decisions/\d{4}-[^/]+\.md\Z")
#: A header line that says a new record overrules an earlier one. A word in the prose does not: a
#: record may say that a later record is the only way it can be overturned, which is the opposite.
SUPERSESSION = re.compile(r"(?im)^[ \t>*_-]*(?:supersedes|amends|overrules|overturns|reverses|replaces|"
                          r"retracts|withdraws)\b[*_]*[ \t]*:")
DECLARATION = re.compile(r"(?im)^[ \t]*[-*][ \t]+[^\n:]*\breview class\b[^:\n]*:[ \t*]*`?([A-Za-z-]+)")
SCOPE_LINE = re.compile(r"(?im)^[ \t]*[-*][ \t]+[^\n:]*\bdecision scope\b[^:\n]*:[ \t]*(\S.*?)[ \t]*$")
CONFORMANCE = "Map and rules conformance"
#: A comparison of more C# files than this is not worth the reads: past it the diff is reviewed.
COMMENT_COMPARE_LIMIT = 40


def on_surface(path, patterns):
    """Whether `path` is on the semantic surface. `**` spans directories; `*` does not."""
    for pattern in patterns:
        regex = re.escape(pattern).replace(r"\*\*/", "(?:.*/)?").replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
        if re.fullmatch(regex, path):
            return True
    return False


# --- what a pull request says ------------------------------------------------------------------


def _section(body, heading):
    """`## heading` of a pull request body, HTML comments removed (the template's guidance lives there)."""
    text = re.sub(r"<!--.*?-->", "", body or "", flags=re.S)
    lines, current = [], None
    for line in text.splitlines():
        found = re.match(r"^##\s+(.*?)\s*$", line)
        if found:
            # A repeated heading restarts the section, as `tools/pr-policy.py`'s own parser does, so the
            # two read one section and a body cannot say one thing to each.
            current = found.group(1)
            if current == heading:
                lines = []
        elif current == heading:
            lines.append(line)
    return "\n".join(lines).strip()


def declared_class(body):
    """The class a pull request body claims on a `review class:` line of its conformance section, or None.

    Returned as written, lower-cased, so an unknown spelling reaches `judge` and is named there.
    """
    found = DECLARATION.search(_section(body, CONFORMANCE))
    return found.group(1).lower() if found else None


def declared_scope(body):
    """What the conformance section's `decision scope:` line says, or None."""
    found = SCOPE_LINE.search(_section(body, CONFORMANCE))
    return found.group(1).strip("` ") if found else None


# --- C#: is a change only to comments and formatting? ------------------------------------------


def code_signature(text):
    """`text` with every comment removed and the amount of whitespace ignored, or None when unprovable.

    Two files with the same signature compile to the same program: a comment is a separator and
    never a token, a string or character literal is kept byte for byte, a preprocessor line is kept
    whole, and whether two tokens are separated is kept while by how much is not (`a+ ++b` and
    `a++ +b` differ). Built on the scanner `reviewscope` already owns for the reference graph.

    **It returns None rather than guess.** A literal or comment that runs to the end of the file
    means the scanner and the compiler disagree about where something ends, and a comment-only
    verdict about text the scanner cannot read is exactly the one that lets code through.
    """
    out, buffer, i, n = [], [], 0, len(text)
    line_start = True

    def flush():
        if buffer:
            chunk = re.sub(r"[ \t\r\f\v]+", " ", "".join(buffer))
            out.append(re.sub(r" ?\n[ \n]*", "\n", chunk))
            buffer.clear()

    while i < n:
        c = text[i]
        if line_start and c in " \t":
            buffer.append(c)
            i += 1
            continue
        if line_start and c == "#":
            end = text.find("\n", i)
            end = n if end < 0 else end
            flush()
            out.append("\x00" + text[i:end].rstrip("\r") + "\x01")
            i = end
            line_start = False
            continue
        line_start = c == "\n"
        if text.startswith("//", i):
            end = text.find("\n", i)
            buffer.append(" ")
            i = n if end < 0 else end
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            if end < 0:
                return None
            buffer.append(" ")
            i = end + 2
        elif c == '"' or (c in "$@" and '"' in text[i:i + 3]):
            end = reviewscope._literal_end(text, i)
            if end >= n:
                return None
            flush()
            out.append("\x00" + text[i:end] + "\x01")
            i = end
        elif c == "'":
            end = reviewscope._char_end(text, i)
            if end > n:
                return None
            flush()
            out.append("\x00" + text[i:end] + "\x01")
            i = end
        else:
            buffer.append(c)
            i += 1
    flush()
    return "".join(out).strip()


def comment_only(base, head):
    """Whether two versions of a C# file differ in comments and formatting alone. Unprovable is False."""
    if base is None or head is None:
        return False
    try:
        before, after = base.decode("utf-8"), head.decode("utf-8")
    except UnicodeDecodeError:
        return False
    if before == after:
        return True
    a, b = code_signature(before), code_signature(after)
    return a is not None and a == b


# --- decision records --------------------------------------------------------------------------


def _text(data):
    try:
        return data.decode("utf-8") if data is not None else None
    except UnicodeDecodeError:
        return None


def _normal(text):
    return re.sub(r"\s+", " ", text).strip()


def decision_record(path, change, base, head):
    """`(class, why)` of one changed decision record.

    A new record binds nothing until the work that builds to it is reviewed, and that work is its
    own pull request with its own entries. So a new record is `decision-record-only` unless its
    header says it overrules another (`**Supersedes:**`), which changes a ruling that is already in
    force. An existing record is different in kind: it may be the one the engine is built to, and
    nothing here can tell a typo from a reversal, so an edit that is more than whitespace, and a
    deletion, is a `semantic-ruling`.
    """
    if change in REMOVALS:
        return SEMANTIC_RULING, "a decision record deleted: a ruling withdrawn"
    new = _text(head)
    if new is None:
        return SEMANTIC_RULING, "a decision record that cannot be read at the head"
    if change == "ADDED":
        found = SUPERSESSION.search(new)
        if found:
            return SEMANTIC_RULING, (f"a new record that says it {found.group(0).strip(' *_->:').lower()} "
                                     f"another: a ruling already in force changes")
        return DECISION_RECORD_ONLY, "a new decision record that overrules none"
    old = _text(base)
    if old is None:
        return SEMANTIC_RULING, "a decision record that cannot be read at the base, so what changed in it is unknown"
    if _normal(old) == _normal(new):
        return DECISION_RECORD_ONLY, "a decision record changed in whitespace alone"
    return SEMANTIC_RULING, ("an existing decision record edited: it may be the ruling the engine is built to, "
                             "and a typo cannot be told from a reversal by a tool")


# --- one path ----------------------------------------------------------------------------------


def factory_class(ownership, name):
    """`path -> generated | managed | lock | retired | engine-owned | None`, from an ownership module.

    The vendored table `factory produce` wrote the files by, so a path is classified by the same
    rows that wrote it. None is a path the table cannot place, and is never taken for the factory's.
    """
    def classify(path):
        try:
            if getattr(ownership, "retired", None) is not None and ownership.retired(path, name) is not None:
                return "retired"
            row = ownership.classify(path, name)
        except Exception:  # noqa: BLE001  (an unplaceable path is not the factory's)
            return None
        if row is None:
            return None
        if row.cls == ownership.ENGINE_OWNED and row.pattern.endswith("/packages.lock.json"):
            return "lock"
        return row.cls
    return classify


def _is_derived(path, fclass):
    """A file the factory writes. The corpus copy is excluded: it is rule text, and is never derived."""
    return not path.startswith("corpus/") and fclass(path) in ("generated", "managed", "lock")


def _path_class(path, change, patterns, read, fclass, compared):
    """`(class, why)` for one changed path, or `(DERIVED, why)` for a file the factory writes."""
    surface = on_surface(path, patterns)
    if _is_derived(path, fclass):
        return DERIVED, "a file the factory writes"
    if not surface:
        return DOCUMENTATION, "not on the semantic surface"
    if DECISION_RECORD.match(path):
        return decision_record(path, change, read(path, "base"), read(path, "head"))
    if path.startswith("docs/decisions/") and path.endswith(".md"):
        return DOCUMENTATION, "a document beside the decision records, which records none"
    if path.startswith("corpus/") or path.startswith("overlay/"):
        return SEMANTIC_IMPLEMENTATION, "the map's interpretation or its source text"
    if path.endswith(".cs") and change not in REMOVALS and change != "ADDED":
        compared[0] += 1
        if compared[0] <= COMMENT_COMPARE_LIMIT and comment_only(read(path, "base"), read(path, "head")):
            return DOCUMENTATION, "C# that differs from its base in comments and formatting alone"
    return SEMANTIC_IMPLEMENTATION, "executable or build-affecting content on the semantic surface"


# --- a regeneration with nothing behind it -----------------------------------------------------


def _json(data):
    try:
        document = json.loads(data.decode("utf-8")) if data is not None else None
    except (UnicodeDecodeError, ValueError):
        return None
    return document if isinstance(document, dict) else None


def _identity(record):
    """The facts of a record that say what rules the engine implements: the maps, the corpora, the randomness."""
    maps = sorted((str(m.get("packageId")), str(m.get("version")), str(m.get("nupkgSha256")))
                  for m in record.get("maps") or [] if isinstance(m, dict))
    corpora = sorted((str(c.get("sourceId")), str(c.get("contentHash")))
                     for c in record.get("corpora") or [] if isinstance(c, dict))
    return {"maps": maps, "corpora": corpora, "randomness": record.get("randomness")}


def regeneration(changed, read, fclass):
    """`(inert, facts)`: whether every change is the factory re-writing what it wrote, with the rules unmoved.

    Inert means all of: every changed path is one the factory writes (so no hand-written file, no
    overlay, no corpus and no retired path rode along); `provenance.json` is among them, because
    a regeneration cannot write a generated file without moving its record; the base and head
    records name the same maps (package, version, package digest), the same corpora (source,
    content hash) and the same randomness, so the rules are the ones that were there; the head
    record says the factory was not dirty; each generated or managed file's head bytes are the
    ones the head record hashes; and a lock file moved only beside the pins that explain it.

    The kernel and the factory may differ: that is what a factory update is. Whether a new factory
    or kernel changed what the engine does is not a thing this can see, and is the gate's to catch
    by running the engine's own tests against a regeneration (`validate.sh full`), which this does
    not replace. A forged record is the same bytes forged and is caught there too.
    """
    facts = []
    foreign = sorted(p for p in changed if not _is_derived(p, fclass))
    if foreign:
        return False, [f"not every changed file is one the factory writes: {', '.join(f'`{p}`' for p in foreign[:5])}"
                       + ("..." if len(foreign) > 5 else "")]
    if "provenance.json" not in changed:
        return False, ["`provenance.json` is not among the changed files, and a regeneration moves it"]
    before, after = _json(read("provenance.json", "base")), _json(read("provenance.json", "head"))
    if before is None or after is None:
        return False, ["`provenance.json` cannot be read at the base or at the head, so what moved is unknown"]
    problems = []
    if _identity(before) != _identity(after):
        for key in ("maps", "corpora", "randomness"):
            if _identity(before)[key] != _identity(after)[key]:
                problems.append(f"the record's {key} differ between the base and the head")
    if (after.get("factory") or {}).get("dirty") is not False:
        problems.append("the head record says the factory was dirty, so the run is not reproducible")
    recorded = {}
    for section in ("generated", "managed"):
        for item in after.get(section) or []:
            if isinstance(item, dict) and isinstance(item.get("path"), str):
                recorded[item["path"]] = item.get("sha256")
    for path in sorted(changed):
        if path == "provenance.json" or fclass(path) == "lock" or changed[path] in REMOVALS:
            continue
        data = read(path, "head")
        if data is None or recorded.get(path) != hashlib.sha256(data).hexdigest():
            problems.append(f"`{path}` is not the bytes the head record hashes for it")
    if any(fclass(p) == "lock" for p in changed) and "RulesFactory.Packages.g.props" not in changed:
        problems.append("a lock file moved without the pins that would explain it")
    if problems:
        return False, problems
    moved = [f"{key} {(before.get(key) or {}).get('version')} -> {(after.get(key) or {}).get('version')}"
             for key in ("factory", "kernel")
             if (before.get(key) or {}).get("version") != (after.get(key) or {}).get("version")]
    facts.append("the maps, the corpora and the randomness are the same at the base and the head"
                 + (f"; {'; '.join(moved)}" if moved else ""))
    return True, facts


# --- the class of a diff -----------------------------------------------------------------------


def classify(changed, patterns, *, read, fclass):
    """The review class of a diff, computed. `changed` maps engine-relative path -> change type.

    `read(path, side)` returns the bytes at `"base"` or `"head"`, or None; `fclass` is
    `factory_class(...)`. Returns a dict: the `class`, the `onSurface` paths, the `semanticFiles`
    (the on-surface paths when the class is semantic, which is what a semantic reviewer is handed),
    the class of every `paths`, the `decisionRecords` among them (what a ruling review is owed on if
    the diff is, or is claimed to be, a ruling), the `reasons`,
    and the `regeneration` facts when that is what made it inert.
    """
    paths, reasons, compared = {}, [], [0]
    for path in sorted(changed):
        try:
            paths[path] = _path_class(path, changed[path], patterns, read, fclass, compared)
        except Exception as error:  # noqa: BLE001  (a path this cannot classify is reviewed)
            paths[path] = (SEMANTIC_IMPLEMENTATION, f"cannot be classified ({error})")
    surface = sorted(p for p in changed if on_surface(p, patterns))
    classes = {cls for cls, _ in paths.values()}
    derived_on_surface = [p for p in surface if paths[p][0] == DERIVED]
    regen = None
    if derived_on_surface and SEMANTIC_IMPLEMENTATION not in classes:
        # A regeneration beside no input that explains it is judged on its own: either the rules
        # provably did not move, or it is an implementation nobody wrote.
        inert, facts = regeneration(changed, read, fclass)
        if inert:
            regen = facts
        else:
            for path in derived_on_surface:
                paths[path] = (SEMANTIC_IMPLEMENTATION, "regenerated, and " + "; ".join(facts))
            classes.add(SEMANTIC_IMPLEMENTATION)
    classes.discard(DERIVED)
    if SEMANTIC_IMPLEMENTATION in classes:
        computed = SEMANTIC_IMPLEMENTATION
    elif SEMANTIC_RULING in classes:
        computed = SEMANTIC_RULING
    else:
        derived_any = any(cls == DERIVED for cls, _ in paths.values())
        named = classes | ({GENERATED_OR_PROVENANCE} if derived_any else set())
        computed = next((c for c in SPECIFICITY if c in named), DOCUMENTATION)
    for path in surface:
        cls, why = paths[path]
        if cls != DERIVED:
            reasons.append(f"`{path}` ({cls}): {why}")
    if regen:
        reasons.extend(regen)
    return {"class": computed, "onSurface": surface,
            "semanticFiles": surface if computed in SEMANTIC else [],
            "paths": {p: cls if cls != DERIVED else GENERATED_OR_PROVENANCE for p, (cls, _) in paths.items()},
            "decisionRecords": sorted(p for p in surface if DECISION_RECORD.match(p)),
            "reasons": reasons, "regeneration": regen}


def judge(result, declared):
    """`(effective class, problems, hints)`: what the diff owes, once the pull request's claim is weighed.

    The computed class is the floor, and the claim moves it only upward or claims an exemption the
    diff shows (module docstring). A `problem` is a claim the diff contradicts, and a finding; a
    `hint` is an exemption nobody claimed, which costs the pull request nothing it did not already
    owe: it is reviewed as it was before the classes existed, and told how to ask for less.
    """
    computed, problems, hints = result["class"], [], []
    surface = bool(result["onSurface"])
    if declared is not None and declared not in CLASSES:
        problems.append(f"`review class: {declared}` is not a class; the classes are {', '.join(CLASSES)}")
        declared = None
    if computed in SEMANTIC:
        effective = computed
        if declared in SEMANTIC and RANK[declared] > RANK[computed]:
            effective = declared
        elif declared is not None and declared != computed and declared not in SEMANTIC:
            problems.append(f"the pull request claims `{declared}`, and this diff is `{computed}`: "
                            + "; ".join(result["reasons"][:3]) + ". A claim cannot lower what the diff computes")
        elif declared == SEMANTIC_RULING and computed == SEMANTIC_IMPLEMENTATION:
            problems.append("the pull request claims `semantic-ruling`, and this diff also changes the "
                            "implementation, which is `semantic-implementation`: " + "; ".join(result["reasons"][:3]))
        return effective, problems, hints
    if declared in SEMANTIC:
        return declared, problems, hints
    if not surface:
        if declared is not None and declared != computed:
            problems.append(f"the pull request claims `{declared}`, and this diff is `{computed}`")
        return computed, problems, hints
    if declared is None:
        hints.append(f"this diff reads as `{computed}` and touches the semantic surface, and says so nowhere: an "
                     f"exemption is claimed, never assumed, so it is reviewed as an implementation. To claim it, "
                     f"add `- review class: {computed}` to `## {CONFORMANCE}`")
        return SEMANTIC_IMPLEMENTATION, problems, hints
    if declared == computed:
        return computed, problems, hints
    problems.append(f"the pull request claims `{declared}`, and this diff is `{computed}`; the claim does not "
                    f"match, so it is reviewed as an implementation")
    return SEMANTIC_IMPLEMENTATION, problems, hints


def semantic_files(result, effective):
    """The files a semantic reviewer is handed for a change judged `effective`: the surface it touches, or none.

    Not `result["semanticFiles"]`, which follows the *computed* class: an exemption nobody claimed
    makes a computed `decision-record-only` an effective `semantic-implementation`, and the reviewer
    of that is owed the files the diff computed as inert as much as any other on the surface.
    """
    return list(result["onSurface"]) if effective in SEMANTIC else []


def owes(effective):
    """What `effective` obliges, from the one table."""
    return dict(OWES[effective])


def describe(result, effective, declared=None):
    """Plain lines saying what the diff is and what that owes. For a gate's output and a packet's first section."""
    wants = owes(effective)
    lines = [f"review class: `{effective}`"
             + (f" (computed `{result['class']}`)" if effective != result["class"] else "")
             + (f", claimed `{declared}`" if declared else "")]
    lines.extend(f"- {reason}" for reason in result["reasons"][:8])
    owed = [name for name, key in (("named entries", "entries"), ("an entry-scoped self-review", "self_review"),
                                   ("a decision-scoped review record", "ruling_review"),
                                   ("a semantic packet", "packet"), ("a semantic verdict", "verdict")) if wants[key]]
    lines.append("- owes: " + (", ".join(owed) if owed else "structural and provenance validation only"))
    return lines
