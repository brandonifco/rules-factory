"""The map as the generator reads it: the merge with the engine's overlay, the correspondence
table, the C# names an entry takes, and the typed contract of one entry.

No C# is written here beyond the names, and nothing here knows what a file looks like. What the
renderers receive is `Model`: the merged map with each entry's C# member, the correspondence row
it matches first, and the locators it cites.

What the types are is decided in one place, `contract()`, and the rule is: **a type comes from
the map where the map declares one, and is `object` where it does not.** Today the map declares
none. No field of an entry names an input, an output, a unit or a value type (docs/corpus-map.md,
"Fields"), and that is deliberate: *a parameter is not a rule, so it gets no entry at all*, and
`dependsOn` is explicitly not a runtime input. So what the generator can type is what the map does
say. Which entry a request belongs to is always known, and becomes the request's nominal type. A
`kind: assertion` entry is resolved from the caller's value for it (row 8), so its request has an
`Asserting(value)` constructor. The value and every output are `object`, because nothing in the
map says otherwise. A map field that did declare a type would change `contract()` and nothing
else.
"""
import re

import csharp
import overlay as overlay_step
import rulings as rulings_step

OWNED = ("status", "implementedIn", "tests")


ROWS = {
    1: ("ScopeOut", "OutsideCurrentScope"),
    2: ("NotBuilt", "UnsupportedRule"),
    3: ("DefinedElsewhere", "MissingRulesData"),
    4: ("BeyondAdapter", "MissingRulesData"),
    5: ("ValueDependencyUnimplemented", "MissingRulesData"),
    6: ("UnresolvedAmbiguity", "RequiresInterpretation"),
    8: ("Assertion", None),
}


STATUSES = {"mapped": "Mapped", "blocked": "Blocked", "implemented": "Implemented", "declined": "Declined"}


# Names an entry's member may not take: members of MapEntries, EntryPoints and Handlers, the classes
# themselves (a member may not share its class's name), and the Requests namespace the
# generated code qualifies.
RESERVED_MEMBERS = {"SourceId", "Baseline", "Entry", "Derived", "Equals", "ReferenceEquals", "GetHashCode", "ToString",
                    "MapEntries", "EntryPoints", "Handlers", "Requests", "Dispatch", "Has", "Hooked"}


class GenerationError(Exception):
    """The map cannot be turned into an engine as it stands."""


# --- the overlay ---------------------------------------------------------------------------


def merge(document, overlay, root=None):
    """merge(package, overlay) per 0015 rules 1-4; refuses on rules 1 and 2, and on an owner's ruling
    or a decline that breaks decision 0027 (rulings.py; `root`, the engine directory, lets it check
    that each ruling's decision record is a file). A ruling never reaches the merge: the map is data."""
    if not isinstance(overlay, dict):
        raise GenerationError(f"the overlay is not an object of entry id -> {', '.join(OWNED)}")
    ids = [e.get("id") for e in document.get("entries") or []]
    for entry_id, item in overlay.items():
        if entry_id not in ids:
            raise GenerationError(f"{overlay_step.path_for(entry_id)} names {entry_id!r}, which the package map "
                                  f"has no entry for")
        if not isinstance(item, dict) or "status" not in item:
            raise GenerationError(f"{overlay_step.path_for(entry_id)} does not set status")
        extra = sorted(set(item) - set(OWNED) - set(rulings_step.KEYS))
        if extra:
            raise GenerationError(f"{overlay_step.path_for(entry_id)} sets {extra}; an engine owns only {', '.join(OWNED)}, "
                                  f"and keeps its owner's {' and '.join(rulings_step.KEYS)} beside them (0027)")
    problems = rulings_step.problems(document, overlay, root)
    if problems:
        raise GenerationError(f"{overlay_step.DIRECTORY}/ breaks decision 0027: " + "; ".join(problems))
    merged = dict(document)
    entries = []
    for entry in document.get("entries") or []:
        item = overlay.get(entry.get("id"))
        if item is None:
            entries.append(entry)
        else:
            base = {k: v for k, v in entry.items() if k not in OWNED}
            base.update({k: item[k] for k in OWNED if k in item})
            entries.append(base)
    merged["entries"] = entries
    return merged


# --- the correspondence table --------------------------------------------------------------


def first_row(entry, by_id):
    """The first correspondence row the entry matches, in table order; None when it matches none."""
    if entry.get("scope") == "out":
        return 1
    if entry.get("status") in ("mapped", "blocked"):
        return 2
    if "definedElsewhere" in entry:
        return 3
    if "beyondAdapter" in entry:
        return 4
    if entry.get("kind") == "operation":
        for dep in entry.get("dependsOn") or []:
            target = by_id.get(dep)
            if isinstance(target, dict) and target.get("kind") == "value" and target.get("status") != "implemented":
                return 5
    ambiguity = entry.get("ambiguity")
    if isinstance(ambiguity, dict) and ambiguity.get("fate") == "unresolved":
        return 6
    if entry.get("kind") == "assertion":
        return 8
    return None


def pascal(entry_id):
    parts = [p for p in re.split(r"[^A-Za-z0-9]+", entry_id) if p]
    name = "".join(p[0].upper() + p[1:] for p in parts)
    if not name or not name[0].isalpha():
        name = "Entry" + name
    if name in RESERVED_MEMBERS:
        name += "Entry"
    return name


def snake(entry_id):
    name = re.sub(r"[^A-Za-z0-9]+", "_", entry_id).strip("_")
    return name if name[:1].isalpha() else "Entry_" + name


class Model:
    """The merged map, in the shape the templates read."""

    def __init__(self, intake, merged, name, rulings=()):
        self.name = name
        # The owner's rulings (0027), from the overlay (rulings.collect): never in `merged`, the map.
        self.rulings = list(rulings)
        # Every package the engine is composed of, ordered by package id so that what the
        # generator writes is a function of the inputs and not of the order they were given in
        # (0067). One package is the ordinary case and reads exactly as it did.
        self.packages = sorted(((p.package_id, p.version) for p in getattr(
            intake, "packages", [intake])), key=lambda pair: pair[0].encode("utf-8"))
        self.package_id, self.version = self.packages[0]
        self.header = csharp.HEADER.format(package=self.named, version="")
        self.superseded = dict(getattr(intake, "superseded", {}) or {})
        self.source_id = merged["corpus"]
        self.randomness = getattr(intake, "randomness", None)
        self.baseline = merged["baseline"]
        entries = merged.get("entries") or []
        by_id = {e["id"]: e for e in entries}
        members = {}
        self.entries = []
        for entry in entries:
            member = pascal(entry["id"])
            if member in members:
                raise GenerationError(f"entries {members[member]!r} and {entry['id']!r} both name the C# member {member}")
            members[member] = entry["id"]
            self.entries.append({"entry": entry, "member": member, "row": first_row(entry, by_id)})
        self.by_id = {item["entry"]["id"]: item for item in self.entries}
        ruling_members = {}
        for ruling in self.rulings:
            member = pascal(ruling["id"])
            if member in ("All", "OwnerRulings"):
                member += "Ruling"
            if member in ruling_members:
                raise GenerationError(f"rulings {ruling_members[member]!r} and {ruling['id']!r} both name the C# member "
                                      f"OwnerRulings.{member}")
            ruling_members[member] = ruling["id"]
            ruling["member"] = member
        for item in self.entries:
            item["locators"] = self._leaf_locators(item, frozenset())

    @property
    def named(self):
        """The packages this engine is composed of, as one line for a generated file's header."""
        return ", ".join(f"{package} {version}" for package, version in self.packages)

    def _leaf_locators(self, item, seen):
        """Every located entry whose passage `item` rests on, as the located entries' members.

        A located entry cites itself. A derived one (0012) has no passage: method.md makes its
        sources' citations its citation, and the sources are premises that entail the fact
        *together*, so citing only the first would say less at runtime than the map knows (#73).
        So the set is every leaf reached through `derivedFrom`, following derived sources down
        to located ones.

        The order is depth-first, in each entry's `derivedFrom` order, and a locator reached a
        second time (two premises sharing one) keeps its first place. That makes the order a
        function of the map alone, and makes the first locator exactly the one the decline
        path cited before (the first leaf of the first source), so a decline's single kernel
        `Locator`, which the registry takes as the first of these, is unchanged.

        check-map.py refuses cycles and dangling sources before a map is packaged; they are
        refused here too, because the generator must not loop or emit a reference to nothing
        if handed a map that skipped the check.
        """
        entry = item["entry"]
        if isinstance(entry.get("locator"), dict):
            return [item["member"]]
        if entry["id"] in seen:
            raise GenerationError(f"derived entry {entry['id']!r} is derived, through a cycle, from itself")
        sources = entry.get("derivedFrom") or []
        if not sources:
            raise GenerationError(f"entry {entry['id']!r} has no locator and no derivedFrom to cite")
        found = []
        for source in sources:
            if source not in self.by_id:
                raise GenerationError(f"derived entry {entry['id']!r} is derived from {source!r}, which the map has no entry for")
            for member in self._leaf_locators(self.by_id[source], seen | {entry["id"]}):
                if member not in found:
                    found.append(member)
        return found

    def locator_of(self, member):
        """The map's locator object for the located entry whose C# member is `member`."""
        for other in self.entries:
            if other["member"] == member and self.located(other):
                return other["entry"]["locator"]
        raise GenerationError(f"no located entry {member}")

    def located(self, item):
        return isinstance(item["entry"].get("locator"), dict)


def contract(model, item):
    """The typed contract of one entry: its request type, output type and handler form.

    The one place a type is decided (see the module docstring): from the map where it declares
    one, `object` where it does not, and today it declares none. The request type is nominal, one
    per entry, because which entry is being resolved is the one thing always known; it carries an
    `Asserting` constructor on a `kind: assertion` entry, whose value is what row 8 resolves to.

    `required` is the handler a correspondence test already demands: an `implemented` entry not
    on row 8. It becomes a partial method the build cannot complete without; every other entry
    gets an optional hook.
    """
    entry = item["entry"]
    return {
        "request": f"{item['member']}Request",
        "request_cs": f"global::{model.name}.Requests.{item['member']}Request",
        "output": "object",
        "asserts": entry.get("kind") == "assertion",
        "required": entry.get("status") == "implemented" and item["row"] != 8,
    }
