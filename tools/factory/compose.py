"""Several map packages, read as one engine's map (#446, decision 0067).

Four maps of SRD 5.2.1 read one pinned corpus and depend on each other. The contract already
composes **corpora** -- one map may cite several, each with its own adapter and its own share of
the extent (0039, 0042) -- and it did not compose **maps**: `intake.py` opened one package and
returned one document.

A composition is a **union with a namespace**, and what it merges it **derives and reports**:

  * **Identity is `(package, entry id)`.** An entry id is unique in a map by the contract and was
    never unique across maps: `round-down` names three entries over these four maps, and two of
    them are different printings of the rule. In a composition an entry is
    `Srd52Combat.round-down` -- the package id's last segment, the separator, the map's own id --
    which is one path segment for `overlay/<id>.json` and pascals to `Srd52CombatRoundDown`. This
    is 0039's answer for units, one level up: identity is qualified by the thing that enumerated
    it. **A single package is not namespaced**, so an engine produced from one map is byte for
    byte what it was.

  * **Supersession is derived from the corpus, never authored.** Thirteen of `srd-52-combat`'s
    `scope: out`, `status: declined` entries name a passage another of these maps holds **in
    scope**: the stub exists because that map's slice stopped short, and a composition containing
    both should answer the rule rather than decline it. What says two entries are the same passage
    is **the span their evidence occupies in the corpus**, not their text and not their citation:

      - text alone merges the two printings of *Round Down*, which is the thing 0030 exists to
        stop;
      - the citation alone misses `resistance` and `resistance-and-vulnerability`, which quote one
        passage under two heading paths, because a path's earlier segments are a prefix test and
        two mappers wrote different chapters above the same line.

    So a declined entry is superseded when its evidence occurs **exactly once** in the corpus, the
    in-scope entry's does too, and the first span lies inside the second. A passage the corpus
    prints more than once cannot be told apart by its words, and the composition **says so and
    supersedes nothing** -- which is what happens to both `round-down` stubs.

What this module does not do is decide anything at runtime. It produces the composed document and
the report; what an engine does with a supersession is the engine's side of 0067.
"""
import re

#: Between the package's name and the map's own entry id. A `.` because `overlay/<id>.json` needs
#: one path segment of letters, digits, `.`, `-` and `_` (overlay.NAME), and `semantics.pascal`
#: splits on every non-alphanumeric, so `Srd52Combat.round-down` is `Srd52CombatRoundDown`.
SEPARATOR = "."

#: Entry fields holding an id of the same map. Rewritten with the ids they name, so a composed
#: document's relations stay inside the package that authored them: `dependsOn` orders work within
#: one mapper's reading, and nothing in the contract lets one map order another's.
ID_LIST_FIELDS = ("dependsOn", "enabledBy", "suspendedBy", "derivedFrom")


class Refused(Exception):
    """These packages do not compose, and the message says which rule they fail."""


def normalise(text):
    return re.sub(r"\s+", " ", text or "").strip()


def slug(package_id):
    """The package's name in an entry id: the package id's last segment."""
    return str(package_id).rsplit(".", 1)[-1]


def qualified(package_id, entry_id):
    return f"{slug(package_id)}{SEPARATOR}{entry_id}"


def namespaced(document, package_id):
    """`document` with every entry id, and every reference to one, qualified by the package."""
    entries = [dict(e) for e in document.get("entries") or [] if isinstance(e, dict)]
    known = {e.get("id") for e in entries}

    def rename(entry_id):
        return qualified(package_id, entry_id) if entry_id in known else entry_id

    for entry in entries:
        if isinstance(entry.get("id"), str):
            entry["id"] = qualified(package_id, entry["id"])
        for field in ID_LIST_FIELDS:
            if isinstance(entry.get(field), list):
                entry[field] = [rename(v) if isinstance(v, str) else v for v in entry[field]]
        if isinstance(entry.get("crossReferences"), list):
            items = []
            for item in entry["crossReferences"]:
                if isinstance(item, dict) and isinstance(item.get("resolvedBy"), str):
                    item = dict(item, resolvedBy=rename(item["resolvedBy"]))
                items.append(item)
            entry["crossReferences"] = items
        continuation = entry.get("continuesDefinition")
        if isinstance(continuation, dict) and isinstance(continuation.get("definedBy"), str):
            entry["continuesDefinition"] = dict(continuation,
                                                definedBy=rename(continuation["definedBy"]))
    return dict(document, entries=entries)


def union(documents):
    """Several (package id, map document) pairs as one document's entries, namespaced.

    The half of a composition that needs no package and no corpus, so the engine's own gate can
    reproduce exactly the map the factory generated from: `map-overlay.py` composes the restored
    packages here before it applies the overlay, and the overlay's file names are the composed ids.
    One document is returned unchanged, ids and all.
    """
    documents = list(documents)
    if len(documents) == 1:
        return documents[0][1]
    entries = [e for package_id, document in documents
               for e in namespaced(document, package_id)["entries"]]
    seen = [e["id"] for e in entries]
    clashing = sorted({e for e in seen if seen.count(e) > 1})
    if clashing:
        raise Refused(f"the composed document holds {len(clashing)} id(s) twice "
                      f"({', '.join(clashing[:3])}); two packages whose names differ only outside "
                      f"their last segment cannot be told apart in an entry id")
    principal = documents[0][1]
    return {"schemaVersion": principal["schemaVersion"], "corpus": principal["corpus"],
            "baseline": principal["baseline"], "entries": entries}


def _compatible(intakes):
    """Refuse packages that are not readings of one ruleset over one corpus.

    Each `intake` already proved its own package internally consistent and its own corpora in
    hand. What cannot be checked inside one package is whether these packages agree, and there are
    four ways they can fail to.
    """
    ids = [i.package_id for i in intakes]
    if len(set(ids)) != len(ids):
        raise Refused(f"the same package is composed twice: "
                      f"{', '.join(sorted({p for p in ids if ids.count(p) > 1}))}. A composition "
                      f"is a union of readings, and one reading counted twice is not a second")

    principals = {(i.map or {}).get("corpus") for i in intakes}
    if len(principals) != 1 or None in principals:
        raise Refused(f"the packages name {len(principals)} principal corpora "
                      f"({', '.join(sorted(str(p) for p in principals))}); a composition is of "
                      f"maps that read one ruleset, and nothing here says how two rulesets' "
                      f"entries would be ordered against each other")

    identities = {}
    for intake in intakes:
        for verified in intake.corpora:
            corpus = verified["corpus"]
            identity = (corpus["hashDerivation"], corpus["contentHash"])
            other = identities.setdefault(verified["sourceId"], (identity, intake.package_id))
            if other[0] != identity:
                raise Refused(
                    f"{intake.package_id} and {other[1]} both cite {verified['sourceId']} and "
                    f"were made from different bytes of it: "
                    f"{identity[0]} {identity[1][:12]} against {other[0][0]} {other[0][1][:12]}. "
                    f"Two readings of two texts compose into a map of neither")

    baselines = {(i.map or {}).get("baseline", {}).get("contentHash") for i in intakes}
    if len(baselines) != 1:
        raise Refused(f"the packages stamp {len(baselines)} different baselines; each map is of a "
                      f"different state of the corpus, and a composition of them would claim a "
                      f"state none of them read")

    randomness = {i.randomness for i in intakes}
    if len(randomness) != 1:
        raise Refused(f"the packages declare randomness {sorted(str(r) for r in randomness)}; "
                      f"0019 makes the posture the corpus's, and one engine cannot be both")


def _spans(text, corpus):
    """Every span the normalised `text` occupies in the normalised `corpus`."""
    needle = normalise(text)
    if not needle:
        return []
    found, at = [], corpus.find(needle)
    while at != -1:
        found.append((at, at + len(needle)))
        at = corpus.find(needle, at + 1)
    return found


def supersessions(entries, corpora_text):
    """(superseded id -> superseding id, and the passages no verdict could be reached for).

    An in-scope entry supersedes a `scope: out`, `status: declined` entry of **another** package
    when both quote one passage and the declined entry's span lies inside the in-scope one's. The
    span is the identity, for the two reasons the module docstring gives, and a quote the corpus
    prints more than once has no span this can name -- so it is reported and nothing is merged.
    """
    placed, repeated = {}, []
    for entry in entries:
        locator = entry.get("locator")
        source = locator.get("sourceId") if isinstance(locator, dict) else None
        corpus = corpora_text.get(source)
        if corpus is None or not entry.get("evidence"):
            continue
        found = _spans(entry["evidence"], corpus)
        if len(found) == 1:
            placed[entry["id"]] = (source, found[0])
        elif found and entry.get("scope") == "out" and entry.get("status") == "declined":
            # Only a declined entry is reported. An in-scope entry whose words the corpus repeats
            # is 0030's ordinary case -- the conditions map quotes "Speed 0. Your Speed is 0 and
            # can't increase." under five conditions, and its heading path says which -- and it was
            # never a candidate to be superseded, so naming it here would bury the two that are.
            repeated.append((entry["id"], len(found)))

    by_id = {e["id"]: e for e in entries}
    superseded = {}
    for entry in entries:
        if entry.get("scope") != "out" or entry.get("status") != "declined":
            continue
        mine = placed.get(entry["id"])
        if mine is None:
            continue
        package = entry["id"].split(SEPARATOR, 1)[0]
        for other, theirs in sorted(placed.items()):
            if other == entry["id"] or other.split(SEPARATOR, 1)[0] == package:
                continue
            candidate = by_id[other]
            if candidate.get("scope") != "in" or theirs[0] != mine[0]:
                continue
            if theirs[1][0] <= mine[1][0] and mine[1][1] <= theirs[1][1]:
                superseded[entry["id"]] = other
                break
    return superseded, sorted(repeated)


class Composition:
    """What `produce` consumes: one document, and every package that made it.

    It carries the fields of one `Intake` that the generator reads, so a composition of one
    package is that package and a composition of several is a map with more entries.
    """

    def __init__(self, intakes, document, superseded, repeated):
        self.packages = list(intakes)
        self.map = document
        self.superseded = superseded
        self.repeated = repeated
        principal = self.packages[0]
        self.randomness = principal.randomness
        self.corpora = [v for i in self.packages for v in i.corpora]
        seen = {}
        for verified in self.corpora:
            seen.setdefault(verified["sourceId"], verified)
        self.corpora = [seen[k] for k in sorted(seen)]

    @property
    def composed(self):
        """Whether this is several packages read as one, or one package read as itself."""
        return len(self.packages) > 1

    def lines(self):
        """What the run says, in the order a reader needs it.

        One package says exactly what intake always said: a composition is what several packages
        are, and an engine of one is not one. Several say so, and then say what composing them
        meant -- which packages, what each entry is now called, and what supersedes what.
        """
        if not self.composed:
            only = self.packages[0]
            return [f"intake passed: {only.package_id} {only.version}, "
                    f"{len(self.map.get('entries') or [])} entries"]
        said = [f"composed {len(self.packages)} package(s) into {len(self.map['entries'])} entries"]
        for intake in self.packages:
            said.append(f"  {intake.package_id} {intake.version}: "
                        f"{len(intake.map.get('entries') or [])} entries, "
                        f"namespaced {slug(intake.package_id)}{SEPARATOR}*")
        for declined, by in sorted(self.superseded.items()):
            said.append(f"  supersedes {declined} with {by}: one passage, declined in one package "
                        f"and mapped in another")
        for entry_id, count in self.repeated:
            said.append(f"  ?  {entry_id}: the corpus prints this evidence {count} times, so no "
                        f"span identifies its passage and nothing here supersedes or is superseded "
                        f"by it (0030)")
        if not self.superseded:
            said.append("  no entry of one package names a passage another holds in scope")
        return said


def compose(intakes, corpora_text=None):
    """Several verified packages as one document, or raise `Refused` saying why they are not one."""
    # Ordered by package id, not by the order `--package` was given in: what the factory generates
    # must be a function of its inputs, and the engine's own gate reads the restored packages from
    # MSBuild, whose item order is its own business (0067).
    intakes = sorted(intakes, key=lambda i: str(i.package_id).encode("utf-8"))
    if not intakes:
        raise Refused("a composition of no package composes nothing")
    _compatible(intakes)
    if len(intakes) == 1:
        only = intakes[0]
        return Composition([only], only.map, {}, [])
    document = union([(intake.package_id, intake.map) for intake in intakes])
    entries = document["entries"]
    superseded, repeated = supersessions(entries, {k: normalise(v)
                                                   for k, v in (corpora_text or {}).items()})
    return Composition(intakes, document, superseded, repeated)
