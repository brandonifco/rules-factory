"""What a semantic review covered, and what a later change invalidates of it (#532, decision 0071).

A verdict used to be all-or-nothing about one commit (0053): it named the head it was formed on,
and a repair commit ended it. Nothing recorded *what* the review had covered, so the only honest
answer to a one-line repair was to review everything again, and a chain of repairs cost

    rounds x size of the accumulated slice

This module is the one statement of the model that replaces that, vendored into every engine as
`scripts/factory/reviewscope.py` so the engine's rails compute with the factory's code:

  * **units** -- every input a review can rest on, each with a fingerprint: a merged map entry
    (`entry:<id>`), an implementation or test file (`file:<path>`), a corpus (`corpus:<id>`), a
    map's frame (`map-frame:<package>`), the charter, the review policy, the factory commit, and
    the files that can change the meaning of everything (`foundational:`, `decision:`,
    `unreadable:`).
  * **claims** -- what a review judges: one per entry of the slice, one per declared invariant.
    Each claim depends on a set of units, computed from the map's dependency fields and a lexical
    reference graph of the engine's C#, and never declared by the implementer.
  * **impact** -- given a prior attestation and the current state, which claims are retained,
    which are invalidated and why, and whether a full review is required and why. "The head
    changed" is not a reason, and nothing here can produce it.
  * **attestations** -- the deterministic record a review leaves, and the one statement of what
    a well-formed one is (`validate_attestation`).
  * the **adversarial self-review** an implementer owes before a reviewer is paid, the **delta
    packet** a bounded review reads, and the **telemetry** that makes the cost observable.

Everything is a function of its arguments: no clock, no environment, no file system. The callers --
`tools/review-scope.py`, `tools/review-packet.py`, `tools/record-verdict.py` in an engine, and the
benchmark and tests here -- read the bytes and hand them in.

Standard library only.
"""
import hashlib
import json
import re

ATTESTATION_FORMAT = 1
SELF_REVIEW_FORMAT = 1
REVIEW_TYPES = ("full", "delta", "final")
COMPREHENSIVE = frozenset({"full", "final"})
RESULTS = ("PASS", "FAIL")
#: A repair that invalidates more than this fraction of the prior claims is reviewed in full: past
#: it, a bounded review is no longer credible as bounded. Engines may set `review.deltaCeiling`.
DEFAULT_DELTA_CEILING = 0.5
#: Below this many prior claims the ceiling does not apply: invalidating one claim of one is what a
#: repair of a one-entry pull request does, and a delta of it is still bounded by the repair's diff.
CEILING_MINIMUM = 4
#: More than this fraction of the slice's entries changed in the map is a map that moved broadly.
BROAD_MAP_CHANGE = 0.5

#: The closed list of reasons a delta returns to a full review (0071 part 3). Each is a fact about
#: the change that a bounded review cannot absorb. The head changing is deliberately not one.
FULL_REASONS = {
    "no-prior-attestation": "nothing has been reviewed yet, so this review is the baseline",
    "prior-attestation-unusable": "the prior is not a valid attestation of this project, or its integrity cannot be proved",
    "legacy-evidence-unscoped": "the prior records no per-claim dependency fingerprints, so its scope cannot be proved",
    "charter-changed": "the semantic reviewer's charter differs from the one the prior review was formed under",
    "review-policy-changed": "the review section of the agent policy differs from the one the prior review was formed under",
    "governing-corpus-changed": "a corpus a reviewed claim cites has a new content hash, so rules may exist that no entry covers",
    "map-frame-changed": "a map differs outside its entries (corpus binding, baseline, extent or schema)",
    "map-changed-broadly": "more than half of the slice's entries changed in the map",
    "factory-recipe-changed": "the engine was re-produced from another factory commit",
    "foundational-file-changed": "a project, props, lock, SDK or package-source file changed, which can change every rule",
    "engine-decision-changed": "a decision record changed, and a decision is authority over every entry",
    "dependency-graph-unbounded": "a changed file is one the dependency graph cannot read",
    "generated-provenance-inconsistent": "a generated file's bytes are not the ones provenance.json records",
    "repair-too-broad": "the repair invalidated more of the prior claims than the delta ceiling allows",
}
#: Named so that a refusal can say why they are refused, not because they are accepted anywhere.
NOT_A_REASON = frozenset({"head-changed", "sha-changed", "commit-changed", "new-head", "head-moved"})

#: Which global unit prefix forces which reason. A global unit is one no single claim owns.
GLOBAL_UNITS = (
    ("charter", "charter-changed"),
    ("policy:review", "review-policy-changed"),
    ("factory", "factory-recipe-changed"),
    ("map-frame:", "map-frame-changed"),
    ("foundational:", "foundational-file-changed"),
    ("decision:", "engine-decision-changed"),
    ("unreadable:", "dependency-graph-unbounded"),
)

#: The twenty classes of defect an implementer attacks before a reviewer is paid (0071 part 7).
#: The id is what a self-review record answers; the question is what the attack asks.
SELF_REVIEW_CLASSES = (
    ("integer-extremes", "What happens at int/long MinValue and MaxValue, and at zero and one either side of every stated bound?"),
    ("overflow-underflow", "Can any arithmetic on a caller-supplied value overflow or underflow, silently or by exception?"),
    ("empty-collections", "What happens when every collection the request carries is empty?"),
    ("invalid-public-input", "What happens with null, default, negative, crafted or out-of-range values at every public entry point?"),
    ("invalid-construction", "Can a value object or enum be constructed invalid (default struct, cast integer, `with` copy) and reach the rule?"),
    ("phase-state-boundaries", "Does the rule hold at the first and last moment of every phase or state it names, and refuse outside them?"),
    ("order-dependence", "Does the answer change with the order of the inputs, or of actions that should commute?"),
    ("partial-mutation-before-refusal", "Is any state changed before a refusal is decided, so a refused request leaves a trace?"),
    ("exception-leakage", "Can any public resolution path throw instead of returning a refusal or an unresolved result?"),
    ("refusal-classification", "Is each non-answer the right one of refused, unresolved and outside scope, with the right reason?"),
    ("missing-content-masking", "Can unavailable or missing content hide a refusal that is already settled by what is present?"),
    ("sentinel-wraparound", "Is any sentinel, wraparound or modular value (turn counters, indices, -1) reachable as a real value?"),
    ("idempotence", "Does repeating the request or action give the same answer, where the rule says it should?"),
    ("immutability", "Can a caller mutate state the engine returned, or state it was handed after validation?"),
    ("caller-controlled-sizes", "Is every size or count the caller controls bounded before it drives work or allocation?"),
    ("exact-min-max", "Are 'at least', 'at most', 'more than' and 'fewer than' each inclusive or exclusive exactly as the corpus says?"),
    ("exclusive-or", "Where the corpus says 'or', is it exclusive or inclusive, and does the code choose the same?"),
    ("count-semantics", "Are 'exactly', 'up to' and 'at least N' counts implemented as the corpus words them?"),
    ("action-dependency-interactions", "Does the rule still hold when the actions or entries it depends on are applied in combination?"),
    ("invalid-intermediate-state", "Can a public API or a record copy produce an intermediate state the rule assumes impossible?"),
)
SELF_REVIEW_IDS = tuple(identifier for identifier, _ in SELF_REVIEW_CLASSES)
SELF_REVIEW_OUTCOMES = ("tested", "not-applicable")
#: The same floor the overlay's mutations are held to (scripts/map-overlay.py): a reason nobody can
#: act on is a placeholder, and a placeholder is not an answer.
PLACEHOLDERS = frozenset({"tbd", "todo", "none", "n/a", "na", "placeholder", "pending", "xxx", "unknown", "later",
                          "fixme", "wip", "?", "-", "same", "ditto", "see above"})

# --- bytes and digests ------------------------------------------------------------------------


def canonical(value):
    """The one byte encoding of a JSON value: sorted keys, no insignificant whitespace, UTF-8."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def fingerprint(value):
    return sha256(canonical(value))


def pretty(value):
    """How an attestation is written to disk: canonical content, indented for a human, one newline."""
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


# --- paths --------------------------------------------------------------------------------------

#: Files that can change the meaning of every rule at once. Matched by basename.
FOUNDATIONAL_NAMES = frozenset({"Directory.Build.props", "Directory.Build.targets", "Directory.Packages.props",
                                "global.json", "NuGet.config", "nuget.config", "NuGet.Config",
                                "packages.lock.json", "RulesFactory.Packages.g.props"})
FOUNDATIONAL_SUFFIXES = (".csproj", ".props", ".targets", ".sln")
IMPLEMENTATION_ROOTS = ("src/", "tests/")
CHARTER = ".claude/agents/rules-conformance.md"
POLICY = ".github/agent-policy.json"
ATTESTATIONS = "reviews/attestations"
SELF_REVIEWS = "reviews/self-review"
INVARIANTS = "reviews/invariants.json"


def is_generated(path):
    return "/Generated/" in path and path.endswith(".g.cs")


def classify(path):
    """What one engine-relative path is to the review model.

    `implementation` -- hand-written C# the lexical graph reads; `generated` -- a function of map
    and overlay, held to provenance.json; `overlay`, `corpus`, `foundational`, `decision`;
    `unreadable` -- on the implementation surface and not C#, so no edge into or out of it can be
    computed; `record` -- review evidence itself; `other` -- nothing a rule can depend on.
    """
    base = path.rsplit("/", 1)[-1]
    if path.startswith("reviews/"):
        return "record"
    if base in FOUNDATIONAL_NAMES or base.endswith(FOUNDATIONAL_SUFFIXES):
        return "foundational"
    if path.startswith("overlay/") and path.endswith(".json"):
        return "overlay"
    if path.startswith("corpus/"):
        return "corpus"
    if path.startswith("docs/decisions/"):
        return "decision"
    if path.startswith(IMPLEMENTATION_ROOTS):
        if is_generated(path):
            return "generated"
        if path.endswith(".cs"):
            return "implementation"
        return "unreadable"
    return "other"


# --- the lexical reference graph ---------------------------------------------------------------

IDENTIFIER = re.compile(r"@?([A-Za-z_][A-Za-z0-9_]*)")
TYPE_DECLARATION = re.compile(
    r"\b(?:class|struct|interface|enum|record)\s+(?:(?:class|struct)\s+)?@?([A-Za-z_][A-Za-z0-9_]*)")
DELEGATE_DECLARATION = re.compile(r"\bdelegate\s+[^;{}()]*?\b@?([A-Za-z_][A-Za-z0-9_]*)\s*(?:<[^;{}()]*>)?\s*\(")
EXTENSION_METHOD = re.compile(
    r"\bstatic\s+[^;{}()=]*?\b@?([A-Za-z_][A-Za-z0-9_]*)\s*(?:<[^;{}()]*>)?\s*\(\s*this\s")
GLOBAL_USING = re.compile(r"^\s*global\s+using\b", re.MULTILINE)


PARTIAL_TYPE = re.compile(r"\bpartial\s+(?:(?:record|readonly|ref|unsafe|abstract|sealed|static|new|public|internal|"
                          r"private|protected)\s+)*(?:class|struct|interface|record)\s+(?:(?:class|struct)\s+)?@?"
                          r"([A-Za-z_][A-Za-z0-9_]*)")
KEYWORDS = frozenset("""abstract as async await base bool break byte case catch char checked class const continue decimal
default delegate do double else enum event explicit extern false finally fixed float for foreach get goto if implicit in
init int interface internal is lock long namespace new null object operator out override params partial private
protected public readonly record ref required return sbyte sealed set short sizeof stackalloc static string struct
switch this throw true try typeof uint ulong unchecked unsafe ushort using var virtual void volatile when where while
yield""".split())


def blank_literals(text):
    """`text` with every comment and every string or character literal's contents replaced by spaces.

    Only for finding where a type's body and its members are: a brace inside `$"{x}"` or a comment
    is not structure. Newlines are kept, so positions still mean lines. Identifiers are read from
    the unblanked text elsewhere, because a name inside a string can still be code.
    """
    out, i, n = list(text), 0, len(text)

    def blank(start, stop):
        for k in range(start, min(stop, n)):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        c = text[i]
        if text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            blank(i, j)
            i = j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            blank(i, j)
            i = j
        elif c == '"' or (c in "$@" and '"' in text[i:i + 3]):
            k = i
            while k < n and text[k] in "$@":
                k += 1
            verbatim = "@" in text[i:k]
            quotes = 0
            while k + quotes < n and text[k + quotes] == '"':
                quotes += 1
            if quotes >= 3:                                   # a raw string literal
                j = text.find('"' * quotes, k + quotes)
                j = n if j < 0 else j + quotes
            else:
                j = k + 1
                while j < n:
                    if text[j] == "\\" and not verbatim:
                        j += 2
                        continue
                    if text[j] == '"':
                        if verbatim and j + 1 < n and text[j + 1] == '"':
                            j += 2
                            continue
                        j += 1
                        break
                    j += 1
            blank(i, j)
            i = j
        elif c == "'":
            j = i + 1
            while j < n and text[j] != "'":
                j += 2 if text[j] == "\\" else 1
            blank(i, j + 1)
            i = j + 1
        else:
            i += 1
    return "".join(out)


def partial_members(text):
    """(the partial types a file declares, the names of the members it declares inside them).

    A partial type is one type written in several files, and its members call each other by bare
    name -- `Clamp(value)`, never `Handlers.Clamp(value)`. So its files are linked by the members
    each declares, not by the type's name: the generator puts every entry's handler in one partial
    class, and linking by that name would make every handler depend on every other one.
    """
    stripped = blank_literals(text)
    types, members = set(), set()
    for match in PARTIAL_TYPE.finditer(stripped):
        types.add(match.group(1))
        opening = stripped.find("{", match.end())
        if opening < 0:
            continue
        depth, head, skipping, i = 1, [], False, opening + 1
        while i < len(stripped) and depth > 0:
            c = stripped[i]
            if c == "{":
                if depth == 1 and not skipping:
                    _member(head, members)
                head, skipping = [], False
                depth += 1
            elif c == "}":
                depth -= 1
                head = [] if depth == 1 else head
            elif depth == 1:
                if c == ";":
                    if not skipping:
                        _member(head, members)
                    head, skipping = [], False
                elif c == "=" and not skipping:
                    _member(head, members)
                    head, skipping = [], True             # an initialiser or an expression body
                elif not skipping:
                    head.append(c)
            i += 1
    return types, members


def _member(head, members):
    text = re.sub(r"\[[^\]]*\]", " ", "".join(head)).strip()
    if not text or re.search(r"\b(?:class|struct|interface|enum|record|delegate|namespace)\b", text):
        return
    method = re.search(r"@?([A-Za-z_][A-Za-z0-9_]*)\s*(?:<[^()]*>)?\s*\(", text)
    names = [method.group(1)] if method else IDENTIFIER.findall(text)[-1:]
    members.update(name for name in names if name not in KEYWORDS)


def declared_names(text):
    """The names a C# file declares that another file could reach it by: its types, its delegates, its
    extension methods, and the members it declares inside a partial type."""
    _, members = partial_members(text)
    return (set(TYPE_DECLARATION.findall(text)) | set(DELEGATE_DECLARATION.findall(text))
            | set(EXTENSION_METHOD.findall(text)) | members)


def reference_graph(files):
    """`{path: sorted paths it depends on}` over the hand-written C# in `files` ({path: bytes}).

    A file depends on every other file that declares a name it mentions. Comments and strings are
    deliberately not stripped from what a file mentions: an interpolated string holds code, and a
    name mentioned in a comment costs one edge too many, never one too few. Over-approximation is
    the direction this errs in, because an edge too many costs review and an edge too few costs
    correctness.

    The one name that is not an edge is a partial type's, when more than one file declares it: those
    files are joined by the members each declares, which is how their code reaches one another.
    """
    texts = {path: data.decode("utf-8", "replace") for path, data in files.items()
             if classify(path) == "implementation"}
    declared, partial_in = {}, {}
    for path, text in texts.items():
        types, _ = partial_members(text)
        declared[path] = declared_names(text)
        for name in types:
            partial_in.setdefault(name, set()).add(path)
    shared = {name for name, paths in partial_in.items() if len(paths) > 1}
    declares = {}
    for path, names in declared.items():
        for name in names - shared:
            declares.setdefault(name, set()).add(path)
    graph = {}
    for path, text in texts.items():
        tokens = set(IDENTIFIER.findall(text))
        graph[path] = sorted({other for name in tokens for other in declares.get(name, ()) if other != path})
    return graph


def global_using_files(files):
    """Hand-written C# files with a `global using`, which reach every file without being named."""
    return sorted(path for path, data in files.items()
                  if classify(path) == "implementation" and GLOBAL_USING.search(data.decode("utf-8", "replace")))


def closure(graph, anchors):
    """Every file reachable from `anchors`, the anchors included, sorted."""
    seen, stack = set(), [a for a in anchors if a in graph]
    while stack:
        path = stack.pop()
        if path in seen:
            continue
        seen.add(path)
        stack.extend(graph.get(path, ()))
    return sorted(seen)


# --- the state of an engine -------------------------------------------------------------------


def map_dependencies(entry):
    """The entry ids one entry's meaning rests on, from the map's own fields."""
    out = []
    for field in ("dependsOn", "enabledBy", "suspendedBy"):
        out += [str(x) for x in entry.get(field) or [] if isinstance(x, str)]
    derived = entry.get("derivedFrom")
    if isinstance(derived, str):
        out.append(derived)
    elif isinstance(derived, list):
        out += [str(x) for x in derived if isinstance(x, str)]
    for reference in entry.get("crossReferences") or []:
        if isinstance(reference, dict) and isinstance(reference.get("resolvedBy"), str):
            out.append(reference["resolvedBy"])
    return out


def entry_closure(entries, entry_id):
    """`entry_id` and every entry it transitively rests on, sorted. Unknown ids are kept: a
    dependency the map names and does not hold is still a dependency, and its unit is absent."""
    seen, stack = set(), [entry_id]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        merged = entries.get(current)
        if merged:
            stack.extend(map_dependencies(merged.get("entry") or {}))
    return sorted(seen)


def resolve_implemented_in(value, paths):
    """The implementation files an overlay's `implementedIn` names, or None when it names none."""
    names = [value] if isinstance(value, str) else [v for v in value or [] if isinstance(v, str)]
    found = set()
    for name in names:
        name = name.strip().lstrip("./")
        if not name:
            continue
        found |= {p for p in paths if p == name or p.endswith("/" + name)}
    return sorted(found) if found else None


def test_names(row):
    return [str(test.get("name")) for test in (row or {}).get("tests") or []
            if isinstance(test, dict) and test.get("name")]


def tokens_of(files, root):
    """`{identifier: sorted paths}` over the hand-written C# under `root`."""
    index = {}
    for path, data in files.items():
        if path.startswith(root) and classify(path) == "implementation":
            for token in set(IDENTIFIER.findall(data.decode("utf-8", "replace"))):
                index.setdefault(token, set()).add(path)
    return {token: sorted(paths) for token, paths in index.items()}


class Snapshot:
    """The review-relevant bytes of one engine at one commit, handed in by the caller.

    `entries` -- {id: {"entry": the map's entry, "overlay": the overlay row or None}}, already
    merged the way the engine merges them (composed ids and all); `slice` -- the entry ids the
    change claims; `files` -- {engine-relative path: bytes} for every file under the semantic
    surface the model reads (src/, tests/, the foundational files, docs/decisions/);
    `generated_recorded` -- {path: sha256} of the generated files provenance.json records; `maps`
    -- [{"packageId", "version", "sha256", "frame"}] where `frame` is the map minus its entries;
    `corpora` -- {sourceId: contentHash}; `charter`, `policy_review`, `factory` -- digests or ids;
    `invariants` -- [{"id", "statement", "anchors"}], anchors being paths or `entry:<id>`;
    `members` -- {entry id: the C# member the generator names it by}, `pascal` of the id when not
    given, which is the generator's own rule for an id with no reserved collision.
    """

    def __init__(self, *, entries, slice, files, maps, corpora, charter, policy_review, factory,
                 generated_recorded=None, invariants=(), members=None):
        self.entries = entries
        self.slice = list(dict.fromkeys(slice))
        self.files = files
        self.maps = maps
        self.corpora = corpora
        self.charter = charter
        self.policy_review = policy_review
        self.factory = factory
        self.generated_recorded = generated_recorded
        self.invariants = list(invariants)
        self.members = members or {entry_id: pascal(entry_id) for entry_id in entries}


def pascal(entry_id):
    """The generator's member name for an entry id (semantics.pascal, less its reserved-word suffix)."""
    parts = [p for p in re.split(r"[^A-Za-z0-9]+", str(entry_id)) if p]
    name = "".join(p[0].upper() + p[1:] for p in parts)
    return name if name and name[0].isalpha() else "Entry" + name


def entry_references(implementation, members):
    """`{path: entry ids the file reaches through generated code}`.

    The generated registry, request types and contracts are not in the reference graph -- they are
    a function of map and overlay, which are units of their own -- so a handler that resolves
    another entry *through* them (`new SpeedLimitRequest(...)`, `Registry.Resolve("speed-limit")`)
    would reach that entry's handler by no edge at all. A file that names an entry's member, its
    request type, or its id as a string literal therefore depends on that entry.
    """
    by_token = {}
    for entry_id, member in members.items():
        by_token.setdefault(member, set()).add(entry_id)
        by_token.setdefault(member + "Request", set()).add(entry_id)
    out = {}
    for path, data in implementation.items():
        text = data.decode("utf-8", "replace")
        tokens = set(IDENTIFIER.findall(text))
        reached = {entry for token in tokens for entry in by_token.get(token, ())}
        reached |= {entry for entry in members if f'"{entry}"' in text}
        out[path] = sorted(reached)
    return out


def state(snapshot):
    """The units, the claims and their dependencies, and what the state says of itself.

    Returns {"units": {unit: digest}, "claims": {claim: [units]}, "anchors": {claim: [notes]},
    "generatedConsistent": bool, "generatedMismatches": [...], "sliceEntries": [...]}. Plain data,
    so it can be written into an attestation as it is.
    """
    units = {"charter": snapshot.charter, "policy:review": snapshot.policy_review, "factory": snapshot.factory}
    for package in snapshot.maps:
        units[f"map-frame:{package['packageId']}"] = fingerprint(package.get("frame"))
    for source, content in (snapshot.corpora or {}).items():
        units[f"corpus:{source}"] = str(content)
    for entry_id, merged in snapshot.entries.items():
        units[f"entry:{entry_id}"] = fingerprint(merged)
    implementation = {}
    for path, data in snapshot.files.items():
        kind = classify(path)
        if kind == "implementation":
            units[f"file:{path}"] = sha256(data)
            implementation[path] = data
        elif kind == "foundational":
            units[f"foundational:{path}"] = sha256(data)
        elif kind == "decision":
            units[f"decision:{path}"] = sha256(data)
        elif kind == "unreadable":
            units[f"unreadable:{path}"] = sha256(data)
    # A `global using` reaches every file without being named in it, so a file that has one is
    # foundational as well as implementation: a change to it cannot be bounded by the graph.
    for path in global_using_files(snapshot.files):
        units[f"foundational:{path}"] = units[f"file:{path}"]

    graph = reference_graph(implementation)
    source_files = sorted(p for p in implementation if p.startswith("src/"))
    test_files = sorted(p for p in implementation if p.startswith("tests/"))
    test_index = tokens_of(implementation, "tests/")

    def files_of(entry_id, notes):
        merged = snapshot.entries.get(entry_id) or {}
        row = merged.get("overlay") or {}
        anchors = []
        if row.get("implementedIn") not in (None, "", []):
            found = resolve_implemented_in(row.get("implementedIn"), source_files)
            if found is None:
                # Conservative expansion: an implementation nobody can find could be anywhere.
                notes.append(f"{entry_id}: implementedIn {row.get('implementedIn')!r} names no file, so it "
                             f"depends on every source file")
                anchors += source_files
            else:
                anchors += found
        for name in test_names(row):
            declaring = test_index.get(name)
            if declaring:
                anchors += declaring
            else:
                notes.append(f"{entry_id}: test {name!r} is declared by no test file, so it depends on "
                             f"every test file")
                anchors += test_files
        return closure(graph, anchors)

    references = entry_references(implementation, snapshot.members)

    def rests_on(entry_ids, notes):
        """Every unit the entries in `entry_ids` rest on: their map closure, the corpora they cite,
        the files their anchors reach, and -- to a fixpoint -- every entry those files reach through
        generated code, with its own closure."""
        needed, todo, seen, files_seen = set(), list(entry_ids), set(), set()
        while todo:
            member = todo.pop()
            if member in seen:
                continue
            seen.add(member)
            for dependency in entry_closure(snapshot.entries, member):
                needed.add(f"entry:{dependency}")
                entry = (snapshot.entries.get(dependency) or {}).get("entry") or {}
                source = (entry.get("locator") or {}).get("sourceId") if isinstance(entry.get("locator"), dict) else None
                if source:
                    needed.add(f"corpus:{source}")
                for path in files_of(dependency, notes):
                    needed.add(f"file:{path}")
                    if path not in files_seen:
                        files_seen.add(path)
                        todo.extend(r for r in references.get(path, ()) if r not in seen)
                todo.extend(d for d in [dependency] if d not in seen)
        return needed

    claims, notes = {}, {}
    for entry_id in snapshot.slice:
        claim = f"entry:{entry_id}"
        claim_notes = []
        needed = rests_on([entry_id], claim_notes)
        claims[claim] = sorted(needed)
        notes[claim] = claim_notes
    for invariant in snapshot.invariants:
        claim = f"invariant:{invariant['id']}"
        claim_notes, needed = [], set()
        for anchor in invariant.get("anchors") or []:
            if anchor.startswith("entry:"):
                needed |= rests_on([anchor[len("entry:"):]], claim_notes)
            elif anchor in implementation:
                paths = closure(graph, [anchor])
                needed |= {f"file:{path}" for path in paths}
                needed |= rests_on(sorted({r for path in paths for r in references.get(path, ())}), claim_notes)
            else:
                claim_notes.append(f"anchor {anchor!r} is neither an entry nor a hand-written file, so the "
                                   f"invariant depends on every source file")
                needed |= {f"file:{path}" for path in closure(graph, source_files)}
        claims[claim] = sorted(needed)
        notes[claim] = claim_notes

    mismatches = []
    if snapshot.generated_recorded is not None:
        for path, data in sorted(snapshot.files.items()):
            if classify(path) == "generated":
                recorded = snapshot.generated_recorded.get(path)
                if recorded != sha256(data):
                    mismatches.append(path)
    return {"units": dict(sorted(units.items())), "claims": dict(sorted(claims.items())),
            "anchors": {k: v for k, v in sorted(notes.items()) if v},
            "generatedConsistent": not mismatches, "generatedMismatches": mismatches,
            "sliceEntries": list(snapshot.slice), "graph": graph}


def claim_digest(current, claim):
    """One digest for one claim's dependencies at this state: what a self-review is bound to."""
    return fingerprint({unit: current["units"].get(unit) for unit in current["claims"][claim]})


def state_digest(current):
    """One digest for the whole semantic state: every unit and every claim's dependency set."""
    return fingerprint({"units": current["units"], "claims": current["claims"]})


# --- impact -----------------------------------------------------------------------------------


class Refused(Exception):
    """Evidence that cannot be used: it is refused, never silently treated as reusable."""


def impact(prior, current, *, ceiling=DEFAULT_DELTA_CEILING, reusable=True):
    """What `current` invalidates of the attestation `prior`, and whether a full review is owed.

    `prior` is a parsed attestation or None; `reusable` is False when the caller could not prove
    its integrity. Returns {"mode": "full"|"delta"|"none", "reasons": [{"code", "detail"}],
    "retained": [claims], "invalidated": {claim: [reasons]}, "new": [claims], "changes": [claims],
    "carriedFindings": [claims], "review": [claims], "changedUnits": [units]}.

    `mode` is `none` only when nothing is invalidated, nothing is new and no reason applies: the
    prior evidence stands whole at the new head. It is never `full` for want of a reason.
    """
    reasons = []

    def reason(code, detail):
        assert code in FULL_REASONS, code
        reasons.append({"code": code, "detail": detail})

    slice_claims = sorted(current["claims"])
    if not current.get("generatedConsistent", True):
        reason("generated-provenance-inconsistent",
               f"{', '.join(current.get('generatedMismatches') or [])} do not hash to what provenance.json records")
    if prior is None:
        reason("no-prior-attestation", "no attestation was given to reuse")
        return _full(reasons, current)
    if not reusable:
        reason("prior-attestation-unusable", "the prior attestation's integrity could not be proved")
        return _full(reasons, current)
    problems = validate_attestation(prior)
    if problems:
        reason("prior-attestation-unusable", "; ".join(problems[:3]))
        return _full(reasons, current)
    evidence = prior.get("evidence") or {}
    if evidence.get("scope") != "scoped" or not isinstance(evidence.get("units"), dict):
        reason("legacy-evidence-unscoped", "the prior attestation records no per-claim dependency fingerprints")
        return _full(reasons, current)

    before = evidence["units"]
    after = current["units"]
    changed = sorted(u for u in set(before) | set(after) if before.get(u) != after.get(u))
    cited_corpora = {u for claim in (prior.get("claims") or []) for u in claim.get("dependencies") or {}
                     if u.startswith("corpus:")}
    for unit in changed:
        for prefix, code in GLOBAL_UNITS:
            if unit == prefix or (prefix.endswith(":") and unit.startswith(prefix)):
                reason(code, f"{unit} is {_movement(before.get(unit), after.get(unit))}")
        if unit in cited_corpora:
            reason("governing-corpus-changed", f"{unit} is {_movement(before.get(unit), after.get(unit))}")

    entries_in_slice = [c for c in slice_claims if c.startswith("entry:")]
    moved_entries = [c for c in entries_in_slice if before.get(c) != after.get(c)]
    if entries_in_slice and len(moved_entries) / len(entries_in_slice) > BROAD_MAP_CHANGE and \
            len(entries_in_slice) >= CEILING_MINIMUM:
        reason("map-changed-broadly", f"{len(moved_entries)} of {len(entries_in_slice)} entries of the slice changed")

    prior_claims = {c["id"]: c for c in prior.get("claims") or [] if isinstance(c, dict) and c.get("id")}
    retained, invalidated, new = [], {}, []
    for claim in sorted(prior_claims):
        if claim.startswith("change:"):
            continue
        recorded = prior_claims[claim].get("dependencies") or {}
        if claim not in current["claims"]:
            invalidated[claim] = ["claim-removed: the slice no longer claims it"]
            continue
        why = [f"unit-changed: {unit}" if unit in after else f"unit-removed: {unit}"
               for unit in sorted(recorded) if after.get(unit) != recorded[unit]]
        why += [f"dependency-added: {unit}" for unit in current["claims"][claim] if unit not in recorded]
        if why:
            invalidated[claim] = why
        else:
            retained.append(claim)
    for claim in slice_claims:
        if claim not in prior_claims:
            new.append(claim)

    # A changed file no claim rests on is still a change somebody must read.
    depended = {unit for claim in current["claims"].values() for unit in claim}
    changes = sorted(f"change:{unit[len('file:'):]}" for unit in changed
                     if unit.startswith("file:") and unit not in depended and unit in after)

    # A finding is answered by review, not by a fingerprint: a claim the parent failed is reviewed
    # again whether or not anything it rests on moved.
    carried = sorted({f.get("claim") for f in (prior.get("findings") or {}).get("blocking") or []
                      if isinstance(f, dict) and f.get("claim") in current["claims"]})
    for claim in carried:
        if claim in retained:
            retained.remove(claim)
            invalidated[claim] = ["blocking-finding: the prior review failed it"]

    total = len([c for c in prior_claims if not c.startswith("change:")])
    lost = len([c for c in invalidated if not c.startswith("change:")])
    # Only a change that would otherwise be a delta can be too broad for one.
    if not reasons and total >= CEILING_MINIMUM and lost / total > ceiling:
        reason("repair-too-broad", f"{lost} of {total} prior claims invalidated, over the ceiling of {ceiling:g}")

    review = sorted(set(invalidated) & set(current["claims"]) | set(new) | set(changes))
    if reasons:
        out = _full(reasons, current)
        out.update({"changedUnits": changed})
        return out
    mode = "delta" if review else "none"
    return {"mode": mode, "reasons": [], "retained": sorted(retained), "invalidated": dict(sorted(invalidated.items())),
            "new": sorted(new), "changes": changes, "carriedFindings": carried, "review": review,
            "changedUnits": changed}


def _full(reasons, current):
    unique = []
    for item in reasons:
        if item not in unique:
            unique.append(item)
    return {"mode": "full", "reasons": unique, "retained": [], "invalidated": {}, "new": [],
            "changes": [], "carriedFindings": [], "review": sorted(current["claims"]), "changedUnits": []}


def _movement(before, after):
    if before is None:
        return "new"
    if after is None:
        return "gone"
    return f"changed ({before[:12]} -> {after[:12]})"


# --- attestations -----------------------------------------------------------------------------


def attestation_digest(document):
    """The attestation's identity: its canonical bytes without the audit block, which holds time."""
    return fingerprint({k: v for k, v in document.items() if k != "audit"})


def build_attestation(*, project, reviewed_commit, base_commit, review_type, reviewer, charter, packet,
                      maps, corpora, current, result, blocking=(), non_blocking=(), evidence_used=(),
                      parent=None, impact_record=None, telemetry=None, audit=None, scoped=True, locators=None):
    """The attestation of one review, as plain data. Deterministic: the same inputs, the same bytes.

    `current` is `state()` at the reviewed commit; `impact_record` is `impact()` against `parent`
    for a delta or a reasoned full review. Which claims were reviewed follows from the type: every
    claim for a full or final review, and the impact's review set for a delta.
    """
    if review_type not in REVIEW_TYPES:
        raise Refused(f"review type {review_type!r} is not one of {', '.join(REVIEW_TYPES)}")
    impact_record = impact_record or {}
    if review_type == "delta":
        reviewed_set = set(impact_record.get("review") or [])
    else:
        reviewed_set = set(current["claims"]) | set(impact_record.get("changes") or [])
    claims = []
    for claim in sorted(set(current["claims"]) | {c for c in reviewed_set if c.startswith("change:")}):
        dependencies = ({f"file:{claim[len('change:'):]}": current["units"].get(f"file:{claim[len('change:'):]}")}
                        if claim.startswith("change:") else
                        {unit: current["units"].get(unit) for unit in current["claims"][claim]})
        claims.append({"id": claim, "status": "reviewed" if claim in reviewed_set else "retained",
                       "dependencies": dependencies})
    reviewed_units = sorted({u for c in claims if c["status"] == "reviewed" for u in c["dependencies"]})
    entries = sorted(c["id"][len("entry:"):] for c in claims if c["status"] == "reviewed" and c["id"].startswith("entry:"))
    document = {
        "attestationFormat": ATTESTATION_FORMAT,
        "project": project,
        "reviewedCommit": reviewed_commit,
        "baseCommit": base_commit,
        "reviewType": review_type,
        "reviewer": reviewer,
        "charter": charter,
        "packet": packet,
        "maps": maps,
        "corpora": corpora,
        "semanticState": state_digest(current),
        "claims": claims,
        "reviewed": {
            "entries": entries,
            "invariants": sorted(c["id"][len("invariant:"):] for c in claims
                                 if c["status"] == "reviewed" and c["id"].startswith("invariant:")),
            "files": sorted(u[len("file:"):] for u in reviewed_units if u.startswith("file:")),
            "corpora": sorted(u[len("corpus:"):] for u in reviewed_units if u.startswith("corpus:")),
            "locators": {entry: (locators or {}).get(entry) for entry in entries if (locators or {}).get(entry)},
            "dependencyScope": reviewed_units,
        },
        "result": result,
        "findings": {"blocking": _findings(blocking), "nonBlocking": _findings(non_blocking)},
        "evidenceUsed": sorted(evidence_used, key=canonical),
        "parent": ({"sha256": attestation_digest(parent), "reviewedCommit": parent.get("reviewedCommit"),
                    "reviewType": parent.get("reviewType"), "result": parent.get("result")}
                   if parent else None),
        "retained": sorted(c["id"] for c in claims if c["status"] == "retained"),
        "invalidated": _invalidated(review_type, parent, impact_record),
        "fullReviewReasons": list(impact_record.get("reasons") or []) if review_type != "delta" else [],
        "evidence": {"scope": "scoped" if scoped else "unscoped",
                     "units": current["units"] if scoped else None},
        "telemetry": telemetry or {},
    }
    if audit:
        document["audit"] = audit
    return document


def _invalidated(review_type, parent, impact_record):
    """Every prior claim this review does not retain, each with the reason it was not.

    A delta says why claim by claim. A full or final review that follows a parent invalidates all of
    the parent's claims at once, and the reason is the review's own: its full-review reasons, or
    the final acceptance review, which rereads everything by design.
    """
    if review_type == "delta":
        return [{"claim": claim, "reasons": list(why)}
                for claim, why in sorted((impact_record.get("invalidated") or {}).items())]
    if not parent:
        return []
    why = ([f"full-review: {r['code']}" for r in impact_record.get("reasons") or []]
           or (["final-acceptance: the whole slice is reread at the merge boundary"] if review_type == "final" else []))
    return [{"claim": claim["id"], "reasons": why} for claim in parent.get("claims") or [] if isinstance(claim, dict)]


def _findings(items):
    out = []
    for index, item in enumerate(items, 1):
        item = dict(item) if isinstance(item, dict) else {"summary": str(item)}
        item.setdefault("id", f"F{index}")
        out.append(item)
    return out


def validate_attestation(document):
    """Every way `document` is not a well-formed attestation, as printable reasons. Empty when it is.

    The one statement of the rule (0071 part 1): the recorder writes nothing that fails it, the
    delta tool reuses nothing that fails it, and the tests hold both to it.
    """
    if not isinstance(document, dict):
        return ["an attestation is a JSON object"]
    out = []
    if document.get("attestationFormat") != ATTESTATION_FORMAT:
        return [f"attestationFormat is {document.get('attestationFormat')!r}; this reads {ATTESTATION_FORMAT}"]
    for field in ("reviewedCommit", "baseCommit"):
        if not isinstance(document.get(field), str) or not re.fullmatch(r"[0-9a-f]{40}", document.get(field) or ""):
            out.append(f"{field} is not a full commit SHA")
    kind = document.get("reviewType")
    if kind not in REVIEW_TYPES:
        out.append(f"reviewType {kind!r} is not one of {', '.join(REVIEW_TYPES)}")
    result = document.get("result")
    if result not in RESULTS:
        out.append(f"result {result!r} is not PASS or FAIL")
    findings = document.get("findings") if isinstance(document.get("findings"), dict) else {}
    blocking = findings.get("blocking") if isinstance(findings.get("blocking"), list) else None
    if blocking is None or not isinstance(findings.get("nonBlocking"), list):
        out.append("findings.blocking and findings.nonBlocking must be lists")
        blocking = []
    if result == "PASS" and blocking:
        out.append(f"a PASS carries {len(blocking)} blocking finding(s); a blocking finding is a FAIL")
    if result == "FAIL" and not blocking:
        out.append("a FAIL names no blocking finding; a failure nobody can act on is not a verdict")
    for finding in blocking:
        if not isinstance(finding, dict) or not str(finding.get("summary") or "").strip():
            out.append("every blocking finding needs a summary")
            break
    claims = document.get("claims")
    if not isinstance(claims, list):
        return out + ["claims is not a list"]
    ids = [c.get("id") for c in claims if isinstance(c, dict)]
    scoped = isinstance(document.get("evidence"), dict) and document["evidence"].get("scope") == "scoped"
    for finding in blocking:
        # The delta after a repair rereads the claims the parent failed. A finding that names no
        # claim of this attestation would leave it nothing to reread, so a scoped one must name one.
        if scoped and isinstance(finding, dict) and finding.get("claim") not in ids:
            out.append(f"blocking finding {finding.get('id')!r} names no claim of this attestation "
                       f"(got {finding.get('claim')!r}); the review after the repair could not know what to reread")
    if len(ids) != len(claims) or len(set(ids)) != len(ids) or ids != sorted(ids):
        out.append("claims must be objects with unique ids, sorted")
    statuses = {c.get("id"): c.get("status") for c in claims if isinstance(c, dict)}
    for claim in claims:
        if isinstance(claim, dict) and claim.get("status") not in ("reviewed", "retained"):
            out.append(f"claim {claim.get('id')!r} has status {claim.get('status')!r}")
    retained = [c for c, s in statuses.items() if s == "retained"]
    if kind in COMPREHENSIVE and retained:
        out.append(f"a {kind} review retains {len(retained)} claim(s); it must review every claim")
    if (document.get("retained") or []) != sorted(retained):
        out.append("retained does not list exactly the claims whose status is retained")
    reasons = document.get("fullReviewReasons")
    if not isinstance(reasons, list):
        out.append("fullReviewReasons is not a list")
        reasons = []
    for item in reasons:
        code = item.get("code") if isinstance(item, dict) else None
        if code in NOT_A_REASON:
            out.append(f"{code!r} is not a reason for a full review: a changed commit alone invalidates nothing")
        elif code not in FULL_REASONS:
            out.append(f"{code!r} is not a full-review reason ({', '.join(sorted(FULL_REASONS))})")
    parent = document.get("parent")
    if kind == "delta":
        if not isinstance(parent, dict):
            out.append("a delta review has no parent attestation")
        if reasons:
            out.append("a delta review carries full-review reasons")
        for entry in document.get("invalidated") or []:
            claim = entry.get("claim") if isinstance(entry, dict) else None
            if claim in statuses and statuses[claim] != "reviewed":
                out.append(f"{claim} was invalidated and not reviewed")
    if kind == "final" and not isinstance(parent, dict):
        out.append("a final review has no parent: a comprehensive review with nothing before it is a full one")
    if kind == "full" and isinstance(parent, dict) and not reasons:
        out.append("a full review with a prior attestation names no reason for not being a delta")
    evidence = document.get("evidence")
    if not isinstance(evidence, dict) or evidence.get("scope") not in ("scoped", "unscoped"):
        out.append("evidence.scope must be scoped or unscoped")
    elif evidence.get("scope") == "scoped":
        units = evidence.get("units")
        if not isinstance(units, dict):
            out.append("a scoped attestation records no units")
        else:
            for claim in claims:
                for unit, digest in ((claim.get("dependencies") or {}).items() if isinstance(claim, dict) else ()):
                    if units.get(unit) != digest:
                        out.append(f"claim {claim.get('id')} records {unit} at a digest the state does not")
                        break
    return out


def check_chain(document, parent):
    """Every way `document` does not follow from `parent`, as printable reasons.

    A delta retains a claim only at the fingerprints its parent recorded, and names every blocking
    finding of the parent as resolved or still open. A final review follows a chain with a delta in
    it. `parent` is the parsed parent attestation.
    """
    out = []
    link = document.get("parent") or {}
    if link.get("sha256") != attestation_digest(parent):
        out.append("the parent digest is not the digest of the parent given")
    parent_claims = {c["id"]: c for c in parent.get("claims") or []}
    for claim in document.get("claims") or []:
        if claim.get("status") != "retained":
            continue
        before = parent_claims.get(claim["id"])
        if before is None:
            out.append(f"{claim['id']} is retained but the parent never reviewed it")
        elif before.get("dependencies") != claim.get("dependencies"):
            out.append(f"{claim['id']} is retained at fingerprints the parent did not record")
    if document.get("reviewType") == "delta" and document.get("result") == "PASS":
        reviewed = {c["id"] for c in document.get("claims") or [] if c.get("status") == "reviewed"}
        for finding in (parent.get("findings") or {}).get("blocking") or []:
            claim = finding.get("claim")
            if claim and claim not in reviewed:
                out.append(f"the parent's blocking finding {finding.get('id')} on {claim} was not reviewed again")
    return out


def check_binding(document, *, recorded_digest, reviewed_commit, maps, project):
    """Every way `document` is not the attestation that was recorded, of this commit, map and project.

    `recorded_digest` is the digest the recorder put in the commit status at `reviewed_commit`, the
    one place outside the file that says what the file was: an attestation edited after it was
    recorded -- a FAIL rewritten as a PASS, a fingerprint changed -- no longer hashes to it. `maps`
    is [{"packageId", "sha256"}] as the reviewed commit's provenance.json declares them; `project`
    the engine's name. An attestation of another commit, map or engine is stale, and is refused.
    """
    out = []
    digest = attestation_digest(document)
    if recorded_digest != digest:
        out.append(f"the attestation hashes to {digest[:12]}, and the status recorded at "
                   f"{str(reviewed_commit)[:12]} names {str(recorded_digest)[:12]}: it was edited after it was "
                   f"recorded, or it is not the one recorded")
    if document.get("reviewedCommit") != reviewed_commit:
        out.append(f"the attestation is of {str(document.get('reviewedCommit'))[:12]}, not {str(reviewed_commit)[:12]}")
    named = sorted((m.get("packageId"), m.get("sha256")) for m in document.get("maps") or [] if isinstance(m, dict))
    declared = sorted((m.get("packageId"), m.get("sha256")) for m in maps)
    if named != declared:
        out.append(f"the attestation names maps {named}, and {str(reviewed_commit)[:12]} declares {declared}")
    if (document.get("project") or {}).get("engine") != project:
        out.append(f"the attestation is of engine {(document.get('project') or {}).get('engine')!r}, not {project!r}")
    return out


def status_for(document, semantic_context):
    """(context, state) a recorded attestation posts. The one place the merge gate's context is chosen.

    A comprehensive PASS -- full or final -- posts the semantic context the gate requires. A delta
    PASS posts `<semantic context>/delta`, which no gate requires: a chain of deltas reaches the
    merge only through one final acceptance review (0071 part 5). Any FAIL posts a failure at the
    semantic context, which blocks.
    """
    if document.get("result") != "PASS":
        return semantic_context, "failure"
    if document.get("reviewType") in COMPREHENSIVE:
        return semantic_context, "success"
    return f"{semantic_context}/delta", "success"


def may_carry(document, impact_record):
    """Whether a verdict may be posted at a new head without a review: a comprehensive PASS whose
    every unit is unchanged there. The reason is the fingerprints, never the commit (0071 part 6)."""
    return (document.get("result") == "PASS" and document.get("reviewType") in COMPREHENSIVE
            and impact_record.get("mode") == "none")


# --- the adversarial self-review ---------------------------------------------------------------


def self_review_skeleton(entry_id, digest):
    """The record an implementer fills in: every class, unanswered."""
    return {"selfReviewFormat": SELF_REVIEW_FORMAT, "entry": entry_id, "claimSha256": digest,
            "classes": {identifier: {"outcome": "", "tests": [], "reason": ""} for identifier in SELF_REVIEW_IDS}}


def _placeholder(text):
    words = re.findall(r"[A-Za-z0-9']+", text.lower())
    stripped = text.strip().lower().strip(".!")
    return (stripped in PLACEHOLDERS or len(words) < 3 or len(text.strip()) < 12
            or len(set(words)) == 1)


def self_review_problems(record, entry_id, digest, declared_tests):
    """Every way `record` does not show the adversarial self-review `entry_id` owes. Empty when it does.

    `digest` is `claim_digest` at the head under review, so a record made before the last repair to
    the claim's closure is stale; `declared_tests` is the set of identifiers the engine's test files
    declare, so a test named here must at least exist.
    """
    if not isinstance(record, dict):
        return [f"{entry_id}: no self-review record"]
    out = []
    if record.get("selfReviewFormat") != SELF_REVIEW_FORMAT:
        out.append(f"{entry_id}: selfReviewFormat is {record.get('selfReviewFormat')!r}, not {SELF_REVIEW_FORMAT}")
    if record.get("entry") != entry_id:
        out.append(f"{entry_id}: the record is for {record.get('entry')!r}")
    if record.get("claimSha256") != digest:
        out.append(f"{entry_id}: the record was made against claim digest {str(record.get('claimSha256'))[:12]}, and "
                   f"the claim is now {digest[:12]}: something it rests on changed since, so attack it again")
    classes = record.get("classes") if isinstance(record.get("classes"), dict) else {}
    for identifier in SELF_REVIEW_IDS:
        answer = classes.get(identifier)
        if not isinstance(answer, dict):
            out.append(f"{entry_id}: {identifier} is not answered")
            continue
        outcome = answer.get("outcome")
        if outcome == "tested":
            tests = [t for t in answer.get("tests") or [] if isinstance(t, str) and t]
            if not tests:
                out.append(f"{entry_id}: {identifier} says tested and names no test")
            missing = [t for t in tests if t not in declared_tests]
            if missing:
                out.append(f"{entry_id}: {identifier} names {', '.join(missing)}, which no test file declares")
        elif outcome == "not-applicable":
            if _placeholder(str(answer.get("reason") or "")):
                out.append(f"{entry_id}: {identifier} is not-applicable with no reason anybody can check")
        else:
            out.append(f"{entry_id}: {identifier} has outcome {outcome!r}; one of {', '.join(SELF_REVIEW_OUTCOMES)}")
    unknown = sorted(set(classes) - set(SELF_REVIEW_IDS))
    if unknown:
        out.append(f"{entry_id}: unknown classes {', '.join(unknown)}")
    return out


# --- the delta packet ----------------------------------------------------------------------------


def measure(text, attachments=()):
    """Deterministic size proxies for what a reviewer is handed: no token count is invented."""
    data = text.encode("utf-8")
    extra = [a.encode("utf-8") if isinstance(a, str) else a for a in attachments]
    return {"bytes": len(data) + sum(len(a) for a in extra), "characters": len(text) + sum(
        len(a.decode("utf-8", "replace")) for a in extra), "files": 1 + len(extra),
        "lines": text.count("\n") + sum(a.count(b"\n") for a in extra)}


def render_delta_packet(*, prior, prior_digest, head, base, current, impact_record, entry_packets, diff,
                        closure_files, locators, tests, charter_path=CHARTER):
    """The delta packet a bounded reviewer reads, as Markdown.

    `entry_packets` is [(entry id, file name, sha256)] for the entries the review set names;
    `diff` the diff from the prior head restricted to the review set's closure; `closure_files`
    {path: sha256} of the files in that closure; `locators` {entry id: locator}; `tests` {entry id:
    [overlay tests]}. Every line is computed from those, the prior attestation and the state: it
    holds no conversation, because nothing it is given is one.
    """
    review = impact_record["review"]
    lines = [f"# Delta review packet: `{head}`\n",
             f"Prior attestation `{prior_digest}` — a **{prior.get('reviewType')}** review of `{prior.get('reviewedCommit')}`, "
             f"result **{prior.get('result')}**. New head `{head}`; base `{base}`.\n",
             "This packet is the whole of your assignment. It is built from the repository, the map and the committed "
             "attestation alone: there is no implementation conversation behind it, and you need none. Start from a "
             f"clean session, read `{charter_path}`, then this, in order.\n",
             "## 1. Why this is a delta, and not a full review\n",
             f"The semantic impact of the change since `{str(prior.get('reviewedCommit'))[:12]}` was computed from the "
             "map's dependency fields, the lexical reference graph of the engine's C#, and the fingerprints of every "
             f"unit the prior review rested on. **{len(review)}** claim(s) must be reviewed; "
             f"**{len(impact_record['retained'])}** are retained unchanged. That the head moved is not, by itself, a "
             "reason to reread anything.\n",
             "## 2. The blocking findings being repaired\n"]
    blocking = (prior.get("findings") or {}).get("blocking") or []
    lines += ([f"- **{f.get('id')}** on `{f.get('claim', '(no claim)')}`: {f.get('summary')}" for f in blocking]
              or ["None: the prior review passed. This delta covers what changed since."])
    lines.append("\nEach must be resolved, or still open, in your verdict. A finding the change did not address "
                 "is still a blocking finding.\n")
    lines.append("## 3. The claims to review, and why each is here\n")
    for claim in review:
        why = (impact_record["invalidated"].get(claim)
               or (["new: the prior review never covered it"] if claim in impact_record["new"] else None)
               or ["changed, and no claim depends on it: read the change itself"])
        lines.append(f"- `{claim}`")
        lines += [f"  - {item}" for item in why]
    lines.append("\n## 4. The entries, as the map has them\n")
    lines.append("Read these **before** the diff: your reading of the rule is formed from the map, never from "
                 "the implementation.\n")
    lines += [f"- `{entry}`: `{name}` (sha256 `{digest}`)" for entry, name, digest in entry_packets] or [
        "No entry claim is in the review set."]
    lines.append("\n## 5. Where they come from\n")
    lines += [f"- `{entry}`: {json.dumps(locator, sort_keys=True, ensure_ascii=False)}"
              for entry, locator in sorted(locators.items())] or ["No locator: no entry claim is in the review set."]
    lines.append("\n## 6. Tests and mutations\n")
    for entry, items in sorted(tests.items()):
        lines.append(f"- `{entry}`")
        lines += [f"  - `{t.get('name')}` — mutation: {t.get('mutation')}" for t in items] or [
            "  - **no test named in the overlay** — that is a finding"]
    lines.append("\n## 7. The implementation in scope\n")
    lines.append("Every hand-written file the review set rests on, by the lexical reference graph. Changed files "
                 "are in the diff below; the others are unchanged since the prior review and are named so that "
                 "you can open them at the reviewed commit when a finding turns on them.\n")
    lines += [f"- `{path}` sha256 `{digest[:16]}`" for path, digest in sorted(closure_files.items())] or ["None."]
    lines.append(f"\n## 8. The diff since `{str(prior.get('reviewedCommit'))[:12]}`, within that scope\n")
    lines.append(diff.rstrip() + "\n" if diff.strip() else "Empty: no file in scope changed, only what the "
                 "claims rest on in the map.\n")
    lines.append("## 9. Evidence retained from the prior review\n")
    lines += [f"- `{claim}`" for claim in impact_record["retained"]] or ["None."]
    lines.append("\nEach of these rests only on units whose fingerprints are unchanged. You are not asked to reread "
                 "them. A defect you notice in one anyway is still a finding: report it.\n")
    lines.append("## 10. Evidence invalidated\n")
    lines += [f"- `{claim}`: {'; '.join(why)}" for claim, why in sorted(impact_record["invalidated"].items())] or ["None."]
    lines.append("\n## 11. What your verdict must say\n")
    lines.append("PASS only if every claim in section 3 holds and every finding in section 2 is resolved. For each "
                 "claim, say which it is. A FAIL names each blocking finding with the claim it is about. A delta PASS "
                 "does not merge anything: a final acceptance review reads the whole slice once, from a clean "
                 "snapshot, before the merge.\n")
    return "\n".join(lines)


# --- telemetry ---------------------------------------------------------------------------------


def chain(attestations):
    """The attestations in review order, following parent links; refused when they do not form one chain."""
    by_digest = {attestation_digest(a): a for a in attestations}
    children = {}
    roots = []
    for digest, document in by_digest.items():
        parent = (document.get("parent") or {}).get("sha256")
        if parent and parent in by_digest:
            children.setdefault(parent, []).append(digest)
        else:
            roots.append(digest)
    ordered = []
    for root in sorted(roots, key=lambda d: (by_digest[d].get("reviewedCommit") or "", d)):
        current = root
        while current:
            ordered.append(by_digest[current])
            nxt = sorted(children.get(current, []))
            current = nxt[0] if nxt else None
    return ordered


def telemetry(attestations):
    """How much review a chain of attestations cost and reused, from the attestations alone."""
    ordered = chain(attestations)
    rounds, categories = [], {}
    repairs_before_pass = None
    for index, document in enumerate(ordered):
        claims = document.get("claims") or []
        reviewed = [c for c in claims if c.get("status") == "reviewed"]
        retained = [c for c in claims if c.get("status") == "retained"]
        blocking = (document.get("findings") or {}).get("blocking") or []
        for finding in blocking:
            category = finding.get("category") or "uncategorised"
            categories[category] = categories.get(category, 0) + 1
        measured = document.get("telemetry") or {}
        rounds.append({
            "reviewType": document.get("reviewType"), "result": document.get("result"),
            "reviewedCommit": document.get("reviewedCommit"),
            "claimsReviewed": len(reviewed), "claimsRetained": len(retained),
            "entriesReviewed": len((document.get("reviewed") or {}).get("entries") or []),
            "invalidated": len(document.get("invalidated") or []),
            "closureSize": len((document.get("reviewed") or {}).get("dependencyScope") or []),
            "findings": len(blocking),
            "nonBlocking": len((document.get("findings") or {}).get("nonBlocking") or []),
            "fullReviewReasons": [r.get("code") for r in document.get("fullReviewReasons") or []],
            **{key: measured.get(key) for key in ("packetBytes", "packetCharacters", "packetFiles", "changedFiles",
                                                  "changedEntries", "tokens")},
        })
        if repairs_before_pass is None and document.get("result") == "PASS":
            repairs_before_pass = index
    count = {kind: sum(1 for r in rounds if r["reviewType"] == kind) for kind in REVIEW_TYPES}
    return {
        "rounds": rounds,
        "fullReviews": count["full"], "deltaReviews": count["delta"], "finalReviews": count["final"],
        "claimsReviewed": sum(r["claimsReviewed"] for r in rounds),
        "claimsReused": sum(r["claimsRetained"] for r in rounds),
        "packetBytes": sum(r["packetBytes"] or 0 for r in rounds),
        "repairsBeforePass": repairs_before_pass,
        "repeatedFindingCategories": {k: v for k, v in sorted(categories.items()) if v > 1},
        "fullReviewReasons": sorted({code for r in rounds for code in r["fullReviewReasons"]}),
        "tokens": (sum(r["tokens"] for r in rounds) if rounds and all(isinstance(r["tokens"], int) for r in rounds)
                   else None),
    }
