#!/usr/bin/env python3
"""The pull request contract, checked mechanically.

    tools/pr-policy.py <pr-number>
    tools/pr-policy.py --docs-skeleton      the `## Documentation` section for this tree, to fill in

Emitted by rules-factory as a managed file (decision 0029), and run by
`.github/workflows/pr-policy.yml` on every open, edit, push and reopen.

**What this is for.** A pull request is where a change stops being the implementer's and becomes
the repository's, and the only thing a reader six months later has is what it said. A vague pull
request is not a formatting problem: it is a change whose behavioural claim nobody stated, whose
evidence nobody can re-run, and whose scope nobody bounded -- and each of those is how a defect
gets merged with everyone's agreement.

So this checks what can be checked mechanically, and nothing it cannot:

  1. exactly one real `Closes #<n>` -- one branch closes one issue;
  2. every mandatory section is present and filled, not left as its placeholder;
  3. the evidence section shows a command and its output, not a claim that it passed;
  4. a change touching the semantic surface names an entry and a locator;
  5. agent provenance says who implemented and who reviewed;
  6. the linked issue carries exactly one risk label and exactly one state label;
  7. every document this engine owns is accounted for, and what is said matches the diff.

**The documentation section (#236).** A change that makes a document untrue is not finished, and
almost none of what makes one untrue is something a parser can see. So the body carries a line per
document, each ticked with a note:

    - [x] `README.md` — updated: the entry table names the altitude limit
    - [x] `docs/how-we-read-the-corpus.md` — checked, no change: it describes the map, not handlers

**Which documents those are is decided from an engine's layout, and is not rules-factory's list.**
Almost every `*.md` a produced engine holds is the factory's -- `AGENTS.md`, `CLAUDE.md`,
`docs/agent-team.md`, the reviewer charters, this pull request's own template -- and `produce`
refuses a hand edit to each, so asking an engine's pull request to account for one would be asking
for a tick nobody here can act on. What is living is what the engine owns: its `README.md`, its own
`docs/`, and any rail it has **adopted** (`factory produce --adopt <path>`), which is engine-owned
from that moment. A numbered decision record under `docs/decisions/` is frozen, for the reason
rules-factory freezes its own: it records what was decided and is superseded, never rewritten. A
fresh engine owns no documents at all, and then this section says so in a sentence -- which is a
true answer, and stops being one the day somebody writes a README.

Whoever owns it, **a document the diff touches is listed as `updated`** -- which catches a README
added in a branch and never mentioned again. An admitted produce claim is the single exception, and
only to that one rule: the claim was granted by showing every changed path is one the factory
writes, which says more than a tick beside twenty rails whose honest note is all the same sentence.
The engine's own documents are listed in a produce update like any other.

This cannot tell whether anyone read a file. That part rests on the author's word, and the note is
where they give it.

**Produce mode (#193).** A `factory produce` update to this engine -- a new map version, a new
kernel pin, a new factory recipe -- is a pull request under these rails like any other, and two of
the obligations above cannot be met honestly by one: it writes no test of its own, so it can name
no mutation, and a map bump regenerates every entry, so it has no single entry id or locator. A
pull request whose body carries the `## Produced by the factory` section and its marker claims to
be one. The claim is **checked, never taken**, and it is closed on three conditions, all of which
must hold:

  1. it says so -- the section, the marker, and three declared facts: factory version, map package
     and version, kernel version;
  2. those facts equal `provenance.json` in the checked-out tree, and that record says the factory
     was not dirty. A produce from a dirty factory is not reproducible, so it is not an update
     anybody can repeat;
  3. every changed path is one the factory writes, classified through this engine's own vendored
     `scripts/factory/ownership.py` -- generated, managed, a `packages.lock.json` a pin change
     re-locks (#94), or the **deletion** of a file under a retired pattern whose base-commit bytes
     are the ones the base commit's `provenance.json` hashed -- the same test the remover applies,
     so the policy and the run agree about who owned a file (#243). One hand-written `.cs`, one
     overlay file, one edit to `.github/agent-policy.json`
     voids the claim, by name, and the pull request is judged as the ordinary pull request it is.

The file set this can ever cover is exactly the set nobody may hand-edit anyway (AGENTS.md section
10), so it grants no new territory. Forging the bytes is caught by `./scripts/validate.sh full`,
which regenerates every `*.g.cs` and compares byte for byte; forging the declaration fails against
`provenance.json`, which is in the diff a reviewer reads.

**Produce mode changes what a pull request must say, never what it must prove.** It waives no
verdict, no `Closes #<n>`, no label rule and no gate run. It replaces the two obligations that do
not apply with two that are harder to fake: the map package and version and what moved, in place of
an entry and a locator; and the produce command, the gate's output and a `factory provenance`
recompute, in place of a named mutation.

**What it cannot check, and does not pretend to.** Whether the behavioural claim is true, whether
the evidence was really run, whether the mutation was really observed to fail, or whether the
named reviewer really reviewed. Those are a reviewer's, and the review verdict recorded against
the head commit is where they land (`tools/record-verdict.py`). A policy check that implied
otherwise would make the pull request look more verified than it is.

Label strings and the semantic surface come from `.github/agent-policy.json`, which the engine
owns. Standard library only, plus `gh` (or `$RULES_ENGINE_GH`).
"""
import argparse
import base64
import binascii
import json
import os
import pathlib
import re
import subprocess
import sys

# The produce claim is classified by the engine's vendored scripts/factory/ownership.py, and an
# imported module leaves its bytecode behind: scripts/factory/__pycache__/, a path no ownership row
# covers, so the checkout that ran this goes dirty and tools/dispatch-agent.sh refuses to open a
# worktree for the next issue (#194). The loader reads this flag when the import happens, so it
# belongs here and not beside the import it disarms.
sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parents[1]
POLICY = ".github/agent-policy.json"
PROVENANCE = "provenance.json"

# The template's headings, and what each is for. A pull request is judged against these names, so
# the template and this list move together (both are managed rails, emitted by the same factory).
SECTIONS = (
    ("Linked issue", "which issue this closes"),
    ("Exact behavioural claim", "what the engine does now that it did not do before"),
    ("Scope, and what this deliberately does not do", "what makes the diff reviewable"),
    ("Map and rules conformance", "the entry, the map version and the locator"),
    ("Tests and evidence", "the commands, and what they printed"),
    ("Documentation", "a line for every document this engine owns, and for every one the diff changes"),
    ("Determinism", "what this change does about anything that reads the machine"),
    ("Decisions and trade-offs", "what you chose and what you rejected"),
    ("Known limitations and unresolved behaviour", "what this does not answer"),
    ("Agent provenance", "who implemented, and who reviewed"),
    ("Unrelated changes", "there are none, or they are named"),
    ("Produced by the factory", "what this run of `factory produce` moved, and from what to what"),
)
# The one heading whose absence is not a finding: almost no pull request is a factory update, and a
# section every author had to write "N/A" into would be noise. Its presence is a claim, though, so
# once it is there it is judged like any other section -- and then checked against the tree.
PRODUCE_SECTION = "Produced by the factory"
OPTIONAL = frozenset({PRODUCE_SECTION})
# Fixed, and matched in the raw body rather than in the parsed section: the template's guidance
# lives in HTML comments, which sections() strips, and so does this.
PRODUCE_MARKER = "<!-- rules-factory-produce -->"
# The three facts a produce update declares, and where provenance.json holds each. A declaration is
# only worth checking because it can be wrong: each of these is in the diff the pull request carries.
PRODUCE_FACTS = (
    ("factory version", lambda record: (record.get("factory") or {}).get("version")),
    # Every map the engine is composed of, in the record's order, which is package id order
    # (rules-factory 0067). One is the ordinary case and reads as it always did.
    ("map package and version",
     lambda record: ", ".join(f"{m.get('packageId')} {m.get('version')}"
                              for m in record.get("maps") or [] if isinstance(m, dict))),
    ("kernel version", lambda record: (record.get("kernel") or {}).get("version")),
)
# Prose, compared against nothing: which of the three moved, and what a reader should expect to see
# in the diff because of it. A produce report (`factory produce --produce-report`) writes all four.
PRODUCE_PROSE = "what moved"
DOCUMENTATION = "Documentation"
# One document's line. The same grammar rules-factory's own tools/check-pr-docs.py reads, so an
# agent that has worked in both writes the same thing in both.
DOCUMENT_LINE = re.compile(
    r"^[-*]\s*\[(?P<tick>[ xX])\]\s*`?(?P<path>[^`\s]+\.md)`?\s*[—–-]+\s*"
    r"(?P<verdict>updated|checked, no change)\s*:\s*(?P<note>.*?)\s*$")
# Frozen by design: a numbered decision record is superseded by a new record, never rewritten.
FROZEN_DOCUMENT = re.compile(r"^docs/decisions/\d{4}-[^/]+\.md$")
# Not the engine's writing and not in its history: what restore, build and test left behind. A
# package's own README unpacked under obj/ is not a document this repository owes anybody a note on.
NOT_A_DOCUMENT_DIRECTORY = frozenset({".git", "bin", "obj", "artifacts", "TestResults", "node_modules"})
CLOSES = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)\b", re.I)
FENCE = re.compile(r"```.*?```", re.S)
# "tests pass", "all green", "CI is happy": a claim in the place the template asks for output.
CLAIM_NOT_EVIDENCE = re.compile(r"^\s*(?:all\s+)?(?:tests?|checks?|ci|gate|validate(?:\.sh)?)\s+"
                                r"(?:pass(?:es|ed|ing)?|are\s+green|is\s+green|green|ok)\s*\.?\s*$", re.I | re.M)


class Failed(Exception):
    """A finding a person has to act on. Every one names what to do."""


def gh(*args):
    command = [os.environ.get("RULES_ENGINE_GH", "gh"), *args]
    done = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=ROOT, timeout=120)
    if done.returncode != 0:
        raise Failed(f"{' '.join(command)} failed: {done.stderr.strip() or done.stdout.strip()}")
    return done.stdout


def policy():
    with open(ROOT / POLICY, encoding="utf-8") as handle:
        return json.load(handle)


def is_semantic(path, patterns):
    """Whether `path` is on the semantic surface. `**` spans directories; `*` does not."""
    for pattern in patterns:
        regex = re.escape(pattern).replace(r"\*\*/", "(?:.*/)?").replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
        if re.fullmatch(regex, path):
            return True
    return False


def sections(body):
    """The body split into `## Heading` -> text, with HTML comments removed.

    The template's guidance lives in comments, so a section that still holds only its comment is
    empty here -- which is the point: a section is filled when somebody wrote in it.
    """
    without_comments = re.sub(r"<!--.*?-->", "", body or "", flags=re.S)
    found = {}
    current = None
    for line in without_comments.splitlines():
        heading = re.match(r"^##\s+(.*?)\s*$", line)
        if heading:
            current = heading.group(1)
            found[current] = []
        elif current is not None:
            found[current].append(line)
    return {name: "\n".join(lines).strip() for name, lines in found.items()}


def check_closes(body, findings):
    """Exactly one `Closes #n`, outside code fences: one branch, one issue, one pull request."""
    prose = FENCE.sub("", re.sub(r"<!--.*?-->", "", body or "", flags=re.S))
    numbers = sorted({number for _, number in ((m.group(0), m.group(1)) for m in CLOSES.finditer(prose))})
    if not numbers:
        findings.append("no `Closes #<n>`: a pull request closes exactly one issue, and says which "
                        "(AGENTS.md section 4). Add it to the Linked issue section.")
    elif len(numbers) > 1:
        findings.append(f"this closes {len(numbers)} issues (#{', #'.join(numbers)}): split it, so that each "
                        f"change can be reviewed, reverted and explained on its own.")
    return numbers[0] if len(numbers) == 1 else None


# The one section a change may honestly answer "N/A": nothing it touches is on the rules surface.
# Whether that is true is not taken on the author's word -- check_conformance decides it from the
# files the pull request actually changes.
MAY_BE_NA = "Map and rules conformance"


def check_sections(body, findings):
    present = sections(body)
    filled = {}
    for name, purpose in SECTIONS:
        empty = {"", "-", "TODO"} if name == MAY_BE_NA else {"", "-", "N/A", "TODO"}
        if name not in present:
            if name in OPTIONAL:
                continue
            findings.append(f"the section `## {name}` is missing ({purpose}). The template is "
                            f".github/pull_request_template.md.")
        elif present[name] in empty:
            findings.append(f"`## {name}` is empty ({purpose}).")
        else:
            filled[name] = present[name]
    return filled


def labelled(text, field):
    """The value written after `<field>:` on its own line, or None. The labels are the template's
    bullets (`- factory version:`), so the word is looked for anywhere in the label, not at its
    start -- the same rule check_conformance and check_provenance read their fields by."""
    found = re.search(rf"(?im)^[^\n:]*\b{re.escape(field)}[^:\n]*:[ \t]*(\S.*?)[ \t]*$", text or "")
    return found.group(1) if found else None


def same_fact(declared, recorded):
    """Whether a declared fact is the recorded one. Whitespace is collapsed, and `Id@Version` is
    accepted for the map beside `Id Version`, because both spellings name the same package and
    `factory produce --package` takes the second."""
    return " ".join((declared or "").replace("@", " ").split()) == " ".join((recorded or "").split())


def engine_ownership():
    """This engine's own `scripts/factory/ownership.py`, and the engine's name (#193).

    Imported from the tree rather than restated here, so the classification a pull request is
    judged by and the one `factory produce` wrote can never disagree: they are one table. A tree
    without it, or without a readable provenance.json, cannot answer the question at all, which is
    why the caller turns that into a finding rather than into an admitted claim.
    """
    with open(ROOT / PROVENANCE, encoding="utf-8") as handle:
        record = json.load(handle)
    name = (record.get("engine") or {}).get("name")
    if not isinstance(name, str) or not name:
        raise Failed(f"{PROVENANCE} names no engine, so no path in this pull request can be classified")
    sys.path.insert(0, str(ROOT / "scripts" / "factory"))
    try:
        import ownership  # noqa: E402  (the factory's ownership table, vendored by produce)
    except ImportError as error:
        raise Failed(f"scripts/factory/ownership.py is not importable ({error}); run `factory produce` again")
    return ownership, name, record


def base_bytes(base_oid, path):
    """The bytes of `path` at the commit this pull request is based on, or None (#243).

    Only read for a path under a retired pattern, so an ordinary pull request makes no extra call.
    Read from the API rather than from the checkout, because the workflow checks out one commit and
    the base is not in it; `{owner}/{repo}` is expanded by `gh` from the current repository. The
    base64 envelope is decoded rather than the raw media type taken, because these bytes are
    hashed and text passed through a pipe is not reliably the bytes that were committed. Any
    failure returns None, and None admits nothing.
    """
    try:
        encoded = gh("api", f"repos/{{owner}}/{{repo}}/contents/{path}?ref={base_oid}", "--jq", ".content")
        return base64.b64decode(encoded)
    except (Failed, OSError, ValueError, binascii.Error):
        return None


def base_record(base_oid):
    """The `provenance.json` of the base commit as a dict, or None."""
    raw = base_bytes(base_oid, PROVENANCE)
    if raw is None:
        return None
    try:
        record = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    return record if isinstance(record, dict) else None


def the_factorys_to_delete(path, base_oid, base, ownership, name):
    """Whether the bytes deleted at `path` are ones the factory is entitled to remove.

    **The same line `ownership.remove_retired` draws**, and it has to be: it is literally the same
    function (`ownership.authorised`), given the base commit's bytes and the base commit's record
    instead of the staging copy's. A retirement is authorised by what the bytes are -- the record
    hashing them as the factory's own output (#243), or a witness showing this run moved them
    somewhere they still are (#247) -- and never by the pathname. A file that was generated once and
    hand-edited afterwards without a re-produce is recorded under its old hash, so the path is in
    the record and the bytes are not the factory's; the remover keeps such a file, and so this must
    refuse its deletion, or the policy and the run would disagree about who owned it. So the base
    bytes are fetched and handed over, not just looked up by name.

    `ROOT` is the head tree the workflow checked out, which is what a witness reads: for the
    overlay's, whether `overlay/` **in this pull request** carries every key the deleted file held.
    """
    data = base_bytes(base_oid, path)
    if data is None:
        return False
    try:
        return ownership.authorised(str(ROOT), path, data, name, base)
    except (ownership.OwnershipError, AttributeError):
        return False


def factory_written(path, change, ownership, name, attributed):
    """Whether `path`, changed as `change` says, is one a `factory produce` run writes.

    Generated and managed files are the factory's on every run. The two `packages.lock.json` are
    engine-owned, and are here for the one case 0018's amendment (#94) admits: a produce that moved
    the generated pins re-locks them, because lock files resolved against the old pins cannot pass
    the gate.

    A **retired** pattern (`ownership.RETIRED`) is one the factory used to write and now deletes, so
    a migration produce's deletions are its work and not somebody's decision carried in beside them.
    That is a narrow admission and it is written narrowly: the change must be a **deletion**
    (`changeType == "REMOVED"`), and `attributed` -- `the_factorys_to_delete`, which calls the same
    `ownership.authorised` the remover does -- must say so of the base commit's bytes at that path.
    A hand-written `backlog/notes.md` matches the pattern too, and so does one the factory wrote and
    somebody has edited since; a `corpus-map.overlay.json` holding a key `overlay/` does not is
    another (#247). Adding, editing or deleting any of them is a decision, and voids the claim like
    any other. Matching the pattern alone was the first version of this and was wrong.

    Everything else an engine owns -- its overlay files, its projects, its rails configuration, its
    hand-written code -- is a decision the factory did not make, and is what voids a claim.
    """
    if getattr(ownership, "retired", None) is not None and ownership.retired(path, name) is not None:
        return change == "REMOVED" and attributed(path)
    row = ownership.classify(path, name)
    if row is None:
        return False
    if row.cls in (ownership.GENERATED, ownership.MANAGED):
        return True
    return row.cls == ownership.ENGINE_OWNED and row.pattern.endswith("/packages.lock.json")


def check_produce(body, filled, changed, findings, base_oid=None):
    """Whether this pull request is a factory update, by the closed predicate #193 decided.

    Returns True only when the section says so, the declared facts are the tree's, and every changed
    path is one the factory writes. A claim that fails any part of that produces a finding naming
    which part: an author who wrote the section meant it, and a silent downgrade would leave them
    reading findings about a mutation they could not have named and wondering which rule they hit.

    `body` is a parameter and not a module global on purpose. This predicate decides what two other
    checks may relax, and a value it read from somewhere else in the process is a value a reader
    cannot follow to its source.
    """
    if PRODUCE_SECTION not in filled and f"## {PRODUCE_SECTION}" not in (body or ""):
        return False
    claim = f"`## {PRODUCE_SECTION}` claims this is a `factory produce` update"
    declared = filled.get(PRODUCE_SECTION) or ""
    if PRODUCE_MARKER not in (body or ""):
        findings.append(f"{claim}, and carries no `{PRODUCE_MARKER}`. The marker is what the section is "
                        f"recognised by; the template writes it, and a section written by hand must keep it.")
        return False

    try:
        ownership, name, record = engine_ownership()
    except (Failed, OSError, ValueError) as error:
        findings.append(f"{claim}, and that claim cannot be checked here: {error}. A claim this check cannot "
                        f"examine is not admitted.")
        return False

    problems = []
    for field, recorded_by in PRODUCE_FACTS:
        value = labelled(declared, field)
        recorded = recorded_by(record)
        if value is None:
            problems.append(f"it declares no {field}")
        elif not same_fact(value, recorded):
            problems.append(f"it declares {field} {value!r}, and {PROVENANCE} in this tree records {recorded!r}")
    if labelled(declared, PRODUCE_PROSE) is None:
        problems.append(f"it does not say {PRODUCE_PROSE}: which of the three moved, and what a reader should "
                        f"therefore expect to find in the diff")
    if (record.get("factory") or {}).get("dirty") is not False:
        problems.append(f"{PROVENANCE} records the factory as dirty, so this engine was produced from a factory "
                        f"checkout with uncommitted changes. Nobody can reproduce that run, so it is not a "
                        f"factory update -- re-produce from a clean factory")

    # Only fetched when the diff holds a retired path, so an ordinary produce update makes no
    # extra call and a failure to fetch is a refusal only where it decides something.
    base, attributed = None, lambda _path: False
    if any(getattr(ownership, "retired", None) is not None and ownership.retired(path, name) is not None
           for path in changed):
        base = base_record(base_oid) if base_oid else None
        if base is None:
            problems.append(f"it changes a file under a retired pattern, and the base commit's {PROVENANCE} "
                            f"could not be read, so whether the factory ever wrote that file is unknown. A "
                            f"deletion this check cannot attribute is not admitted")
        else:
            attributed = lambda path: the_factorys_to_delete(path, base_oid, base, ownership, name)  # noqa: E731
    smuggled = []
    for path in sorted(changed):
        try:
            if not factory_written(path, changed[path], ownership, name, attributed):
                smuggled.append(path)
        except ownership.OwnershipError as error:
            smuggled.append(f"{path} ({error})")
    if smuggled:
        problems.append(f"{len(smuggled)} changed file(s) are not files a produce writes: "
                        f"{', '.join(smuggled[:5])}{'...' if len(smuggled) > 5 else ''}. A produce writes the "
                        f"generated and managed files, re-locks the lock files, and deletes what it recorded "
                        f"under a retired pattern; anything else in this diff is "
                        f"somebody's decision, and it is reviewed as one")

    if problems:
        findings.append(f"{claim}, and it is not one: {'; '.join(problems)}. The claim is void and this pull "
                        f"request is judged as the ordinary pull request it is. Nothing here is waived by the "
                        f"section being present.")
        return False
    return True


def check_evidence(filled, findings, produce=False):
    evidence = filled.get("Tests and evidence")
    if evidence is None:
        return
    fences = FENCE.findall(evidence)
    body = "\n".join(fences)
    if not fences:
        findings.append("`## Tests and evidence` shows no command and no output. Paste what you ran and what it "
                        "printed: a claim is not evidence, and a reviewer cannot re-run a summary.")
    elif not re.search(r"(?m)^\s*(?:\$\s*)?\S*(?:validate\.sh|dotnet|python3|pytest)\b", body):
        findings.append("`## Tests and evidence` shows no command that was run. The gate is "
                        "`./scripts/validate.sh full`; show it, and what it printed.")
    if CLAIM_NOT_EVIDENCE.search(evidence) and len(body.strip().splitlines()) < 3:
        findings.append("`## Tests and evidence` says the tests pass rather than showing them passing. "
                        "This repository has twice shipped a check that counted work it had not done.")
    # Asked whatever the fences hold: the mutation obligation is about the tests, not the formatting.
    if produce:
        # A produce writes no test of its own, so there is no mutation it could honestly name -- and a
        # rule met by writing the word is worse than no rule. What replaces it is not lighter: the
        # command that made these bytes, and a recompute saying the committed record is the one a
        # re-produce writes. Both are re-runnable by a reviewer; "mutation" is not.
        for command, why in (("factory produce", "the command that wrote these bytes"),
                             ("factory provenance", "the recompute showing the committed record is the one a "
                                                    "re-produce writes")):
            if command not in evidence:
                findings.append(f"`## Tests and evidence` shows no `{command}`, and this is a factory update: "
                                f"show {why}, and what it printed. A produce update names no mutation because it "
                                f"writes no test; this is what it shows instead.")
    elif "mutation" not in evidence.lower():
        findings.append("`## Tests and evidence` names no mutation. Every test records the mutation that makes it "
                        "fail, and you must have watched it fail -- a test nobody has watched fail is not yet a test.")


def documents(root):
    """Every `*.md` in the tree, as repository-relative paths."""
    found = []
    for directory, subdirs, files in os.walk(root):
        subdirs[:] = sorted(name for name in subdirs if name not in NOT_A_DOCUMENT_DIRECTORY)
        for name in sorted(files):
            if name.endswith(".md"):
                found.append(os.path.relpath(os.path.join(directory, name), root).replace(os.sep, "/"))
    return sorted(found)


def living_documents(ownership, name, adopted):
    """The documents this engine owns: the ones a change made here can make untrue.

    Everything the factory writes is excluded, because `produce` refuses a hand edit to it: a tick
    beside a file nobody in this repository may change is a tick nobody can act on. An **adopted**
    rail is excluded from that exclusion -- adoption is the engine taking the file as its own
    (decision 0018), and an engine that has adopted `AGENTS.md` owns `AGENTS.md`. A numbered
    decision record is frozen.

    A file whose ownership cannot be decided is treated as the engine's. The direction matters:
    the cost of a wrong answer here is one extra line in a pull request, and the cost the other way
    is a document nobody was asked about.
    """
    living = []
    for path in documents(str(ROOT)):
        if FROZEN_DOCUMENT.match(path):
            continue
        try:
            row = ownership.classify(path, name)
        except ownership.OwnershipError:
            row = None
        if row is not None and row.cls in (ownership.GENERATED, ownership.MANAGED) and path not in adopted:
            continue
        living.append(path)
    return living


def check_documentation(filled, changed, findings, truncated=False, produce=False):
    """Every document this engine owns is listed, and what is said about each matches the diff.

    Returns how many living documents there are, for the summary; None when the section is absent
    (check_sections has already said so) or when ownership could not be read.

    A truncated file list decides nothing about the diff, so the changed-file rules are skipped
    there and the living-document rules -- which read the tree, not the list -- still hold.

    **An admitted produce claim relaxes one rule and no other:** that every changed `*.md` be
    listed. It can, because the claim was only admitted after every changed path was shown to be
    one the factory writes -- which says more about `AGENTS.md` and a retired `backlog/*.md` than a
    tick beside them would, and the tick's honest note is "the recipe this produce brought", twenty
    times over. What is not relaxed is the engine's own documents: an adopted rail is living and is
    still listed, and a produce cannot smuggle a README past this, because a README in the diff
    voids the claim before this check runs.
    """
    section = filled.get(DOCUMENTATION)
    if section is None:
        return None
    try:
        ownership, name, _ = engine_ownership()
    except (Failed, OSError, ValueError) as error:
        findings.append(f"`## {DOCUMENTATION}` cannot be judged here: {error}. Which documents this engine owns "
                        f"is read from its own vendored ownership table and provenance.json, and a section this "
                        f"check cannot examine is not admitted.")
        return None
    living = living_documents(ownership, name, ownership.adopted(str(ROOT)))
    changed_documents = sorted(path for path in changed if path.endswith(".md"))

    listed = {}
    for line in section.splitlines():
        line = line.strip()
        if not line:
            continue
        match = DOCUMENT_LINE.match(line)
        if not match:
            if line.startswith(("-", "*")):
                findings.append(f"`## {DOCUMENTATION}` cannot read {line!r}. One line per document: "
                                f"- [x] `path.md` — updated: what you changed, or "
                                f"- [x] `path.md` — checked, no change: what you looked for.")
            continue
        path = match["path"]
        if path in listed:
            findings.append(f"`{path}` is listed twice in `## {DOCUMENTATION}`.")
        listed[path] = match
        if match["tick"] == " ":
            findings.append(f"`{path}` is not ticked in `## {DOCUMENTATION}`: an unticked line is a document "
                            f"nobody has read against this change.")
        if not match["note"]:
            findings.append(f"`{path}` has no note after `{match['verdict']}:`. Nothing can tell whether you "
                            f"read a file; the note is where you say what you looked for.")

    for path in living:
        if path not in listed:
            findings.append(f"`{path}` is a living document of this engine and is not listed in "
                            f"`## {DOCUMENTATION}`. `tools/pr-policy.py --docs-skeleton` prints the section.")
    if not truncated:
        for path in changed_documents:
            if path not in listed:
                if produce:
                    continue
                findings.append(f"`{path}` is changed by this pull request and is not listed in "
                                f"`## {DOCUMENTATION}`. A document the diff touches is accounted for whoever "
                                f"owns it: the one exception is an admitted factory update, which has already "
                                f"shown every changed path is one the factory writes.")
            elif listed[path]["verdict"] != "updated":
                findings.append(f"`{path}` is changed by this pull request but listed as checked, no change.")
    for path, match in listed.items():
        if truncated:
            break
        if path not in living and path not in changed_documents:
            findings.append(f"`{path}` is neither a living document of this engine nor changed here. "
                            f"A path that is neither is a typo, and a typo ticks nothing.")
        elif match["verdict"] == "updated" and path not in changed_documents:
            findings.append(f"`{path}` is listed as updated but this pull request does not change it.")
    return len(living)


def changed_documents_here():
    """The `*.md` this branch changes against its base, when git can say, and none when it cannot.

    Only `--docs-skeleton` uses this: the skeleton is written before the pull request exists, so
    there is no file list to read. A tree git cannot answer about still gets its living documents
    listed, with the missing half named on stderr rather than passed off as "nothing changed".
    """
    for base in ("origin/main", "main"):
        found = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--verify", "--quiet", base],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if found.returncode != 0:
            continue
        diff = subprocess.run(["git", "-C", str(ROOT), "diff", "--name-only", "--no-renames", f"{base}...HEAD"],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if diff.returncode == 0:
            return sorted(path for path in diff.stdout.splitlines() if path.endswith(".md"))
    print("pr-policy: git could not say what this branch changes, so every line below reads `checked, no "
          "change`; mark as `updated` each document this pull request edits.", file=sys.stderr)
    return []


def print_documentation_skeleton():
    """The `## Documentation` section for this tree, unticked, for the author to complete."""
    try:
        ownership, name, _ = engine_ownership()
    except (Failed, OSError, ValueError) as error:
        print(f"pr-policy: cannot list this engine's documents -- {error}", file=sys.stderr)
        return 2
    living = living_documents(ownership, name, ownership.adopted(str(ROOT)))
    changed = changed_documents_here()
    print(f"## {DOCUMENTATION}")
    print()
    if not living and not changed:
        print("None: this engine has no documents of its own, and nothing here changes one.")
        return 0
    for path in sorted(set(living) | set(changed)):
        print(f"- [ ] `{path}` — {'updated' if path in changed else 'checked, no change'}: ")
    return 0


def check_conformance(filled, semantic_files, findings, produce=False):
    conformance = filled.get("Map and rules conformance")
    if conformance is None or not semantic_files:
        return
    # A map version bump regenerates every entry, so a factory update has no single entry id and no
    # single locator: the honest answers are "all of them" and "the whole map", which name nothing.
    # What it does have is the map package and the version it moved to, which is the fact the diff
    # can be read against -- and that is required here, not waived.
    fields = ((("map", "the map package and version this engine was produced from"),) if produce else
              (("entry", "the entry id, which is what ties this to the map"),
               ("map", "the map package and version this was implemented against"),
               ("locator", "the locator, which is where the rule is")))
    if re.fullmatch(r"(?i)\s*n/?a\.?\s*", conformance):
        findings.append(f"`## Map and rules conformance` says N/A, but this change touches the semantic surface "
                        f"({', '.join(sorted(semantic_files)[:3])}...). Name {', '.join(w for _, w in fields)}: "
                        f"an implementation of an unnamed rule cannot be reviewed against one.")
        return
    for field, what in fields:
        # The template's bullets read "entry id(s):", "map package and version:", "source
        # locator(s):" -- so the word is looked for anywhere in the label, not at its start.
        if labelled(conformance, field) is None:
            findings.append(f"`## Map and rules conformance` does not name {what}.")


def check_provenance(filled, findings):
    provenance = filled.get("Agent provenance")
    if provenance is None:
        return
    for field in ("implemented by", "structurally reviewed by", "semantically reviewed by"):
        if not re.search(rf"(?im)^[^\n:]*\b{re.escape(field)}[ \t]*:[ \t]*\S", provenance):
            findings.append(f"`## Agent provenance` does not say who this was {field.replace(' by', '')} by. "
                            f"A merged commit must say who did what without opening a transcript.")


def check_issue_labels(number, settings, findings):
    issue = json.loads(gh("issue", "view", str(number), "--json", "number,state,labels"))
    names = {label["name"] for label in issue.get("labels") or []}
    labels = settings.get("labels") or {}
    risks = names & {labels.get("normalRisk"), labels.get("independentRisk")}
    states = names & {labels.get("ready"), labels.get("blocked"), labels.get("needsDecision")}
    if len(risks) != 1:
        findings.append(f"issue #{number} carries {len(risks)} risk labels ({', '.join(sorted(risks)) or 'none'}); "
                        f"exactly one is required, because it decides whether an independent verdict is needed.")
    if len(states) != 1:
        findings.append(f"issue #{number} carries {len(states)} state labels ({', '.join(sorted(states)) or 'none'}); "
                        f"exactly one is required.")
    if labels.get("needsDecision") in names:
        findings.append(f"issue #{number} is {labels['needsDecision']}: the question it raises is not answered, and "
                        f"an implementation cannot answer it for itself (AGENTS.md section 6).")
    return issue


def truncation(pull, changed, findings):
    """Whether `gh pr view --json files` gave a partial list (#193). True means decide nothing from it.

    The cap is real and silent: `gh pr view --json files` returns at most 100 files, with no error
    and no warning, whatever `changedFiles` says. Every rule below reads the changed paths -- what
    is on the semantic surface, and whether a produce claim covers the whole diff -- so a pull
    request with more than a hundred changed files whose rule-bearing ones sort past the first
    hundred would be judged on a diff that is not the diff. A map version bump regenerates hundreds
    of files, which is exactly the case this check is for. So the count is asked for alongside the
    list, and a short list refuses rather than deciding on the half it was given: a check that
    examines some of what it is for is not a pass either.
    """
    count = pull.get("changedFiles")
    if not isinstance(count, int) or len(changed) == count:
        return False
    findings.append(f"GitHub returned {len(changed)} of this pull request's {count} changed files: the list is "
                    f"truncated, and the semantic surface and the ownership of this diff cannot be decided from "
                    f"a partial list. Nothing below was judged against the files that are missing. Read the diff "
                    f"(`gh pr diff {pull.get('number')} --name-only`) and split the change, or say on the issue "
                    f"why one pull request this large is the reviewable unit.")
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(prog="pr-policy.py", description=__doc__.split("\n")[0])
    parser.add_argument("pr", type=int, nargs="?", help="the pull request number")
    parser.add_argument("--docs-skeleton", action="store_true",
                        help="print the `## Documentation` section for this tree, unticked, and exit")
    args = parser.parse_args(argv)

    if args.docs_skeleton:
        return print_documentation_skeleton()
    if args.pr is None:
        parser.error("a pull request number is required (or --docs-skeleton)")

    findings, living = [], None
    try:
        settings = policy()
        pull = json.loads(gh("pr", "view", str(args.pr), "--json",
                             "number,title,body,files,changedFiles,baseRefOid"))
        body = pull.get("body") or ""
        # path -> how it changed, as GitHub reports it (ADDED, MODIFIED, REMOVED, RENAMED...). The
        # produce predicate needs it: a retired path is the factory's when deleted and nobody's
        # otherwise. An absent changeType reads as "" and is therefore never a deletion.
        changed = {f["path"]: f.get("changeType") or "" for f in pull.get("files") or []}
        truncated = truncation(pull, changed, findings)
        semantic_files = {path for path in changed
                          if is_semantic(path, (settings.get("review") or {}).get("semanticPaths") or [])}

        linked = check_closes(body, findings)
        filled = check_sections(body, findings)
        # Never on a truncated list: the produce predicate says every changed path is one the
        # factory writes, and a list that is missing some cannot say that about the ones it lost.
        produce = False if truncated else check_produce(body, filled, changed, findings,
                                                        pull.get("baseRefOid"))
        check_evidence(filled, findings, produce=produce)
        check_conformance(filled, semantic_files, findings, produce=produce)
        living = check_documentation(filled, changed, findings, truncated=truncated, produce=produce)
        check_provenance(filled, findings)
        if linked is not None:
            check_issue_labels(linked, settings, findings)
    except Failed as error:
        print(f"pr-policy: cannot check PR #{args.pr} -- {error}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as error:
        print(f"pr-policy: cannot check PR #{args.pr} -- {error}", file=sys.stderr)
        return 2

    if findings:
        print(f"pr-policy: PR #{args.pr} does not satisfy the contract ({len(findings)} finding(s)):\n")
        for finding in findings:
            print(f"  X  {finding}\n")
        print("The contract is .github/pull_request_template.md and AGENTS.md. None of this is about form: each "
              "line above is something a reviewer would otherwise have to take on trust.")
        return 1
    print(f"pr-policy: PR #{args.pr} satisfies the contract "
          f"({len(SECTIONS) - len(OPTIONAL)} required sections, one linked issue, evidence and provenance present, "
          f"{living if living is not None else 0} living document(s) accounted for).")
    if produce:
        print(f"The `## {PRODUCE_SECTION}` claim was admitted: the declared factory, map and kernel are "
              f"{PROVENANCE}'s, that record is not dirty, and every changed file is one a produce writes. "
              f"It replaced the mutation and the entry, and waived no verdict.")
    print("What this does not say: that the claim is true, that the evidence was run, or that the named reviewers "
          "reviewed. Those are the review verdict's, recorded against the head commit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
