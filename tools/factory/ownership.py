"""Who owns each file `produce` writes (#72, decision 0018). One table, three classes.

Before this module the factory had generated files, a one-shot template scaffold and nothing
saying which was which: global.json, NuGet.config and Directory.Build.props were written once
and then belonged to the engine, so a factory change to SDK policy, package sources, analyzers
or target frameworks never reached an engine that had already been produced. `TABLE` below is
now the only place a file's class is decided; generate.py, provenance.py and the tests read it,
and the ADR's table is checked against it.

  * **generated** -- rewritten on every `produce` from the factory's inputs. A hand edit is
    overwritten, and provenance.json hashes each one in `generated`, so an edit made after the
    last `produce` is a named mismatch.
  * **managed** -- factory policy the engine should keep receiving. Each managed file has a
    recipe version, and `RECIPE_SHA256` lists the SHA-256 of the bytes every version of its
    recipe ever wrote. On each `produce` a managed file that is absent, or whose bytes are one
    of those versions, is (re)written from the current recipe: that is the migration. A managed
    file whose bytes are none of them has been edited by hand, and `produce` refuses, naming
    it, before anything is written, rather than overwrite a deliberate change or silently keep
    a stale policy. Two flags settle it: `--adopt PATH` makes the file engine-owned from then
    on (provenance.json records the adoption, so later runs remember it), and `--reset PATH`
    overwrites it with the current recipe and makes it managed again (also how an adopted file
    comes back). provenance.json hashes each managed file once, in `managed`, with its recipe
    version.
  * **engine-owned** -- written once, when absent, and never touched again: the engine's own
    choices, which no factory change should undo. provenance.json lists them in `engineOwned`
    and hashes them, as it hashes every build input the engine owns, in `buildInputs`.

Detection compares against the recipe history in code rather than against the hash the last
`produce` recorded in provenance.json. The history does not trust a file in the engine (an edited
provenance.json cannot make a hand edit look like the factory's), it works for an engine produced
before this module existed (its files are version 1), and it makes a recipe version mean fixed
bytes: tools/tests/test_factory_ownership.py fails when a recipe changes without a new version and
its hash. The cost is that a managed recipe may not depend on the engine's name or the map, and
none does.

Anything `produce` writes must match exactly one row; provenance.build refuses a written path
that matches none, so a new output cannot ship unclassified. The lock files are the one output
not written by Python: verify's first restore (verify.py) writes them in the staging copy when
none exist, and produce commits them. They are engine-owned: no later produce rewrites them, and
the engine relocks (`scripts/validate.sh lock`) and commits them itself. Files the engine adds itself (its
hand-written code, lock files) match no row and are not the factory's to classify.

Standard library only; vendored into every engine as scripts/factory/ownership.py because
generate.py imports it and the engine's gate imports generate.py.
"""
import collections
import fnmatch
import hashlib
import json
import os

GENERATED = "generated"
MANAGED = "managed"
ENGINE_OWNED = "engine-owned"
CLASSES = (GENERATED, MANAGED, ENGINE_OWNED)
PROVENANCE = "provenance.json"

Row = collections.namedtuple("Row", "pattern cls recipe reason")

# `{name}` is the engine name; `*` matches within one path segment only.
TABLE = (
    Row("provenance.json", GENERATED, None,
        "the record of this run; written last, from the run itself"),
    Row("RulesFactory.Packages.g.props", GENERATED, None,
        "the kernel and map pins and the map reference: facts about the inputs (#66)"),
    Row("src/{name}/Generated/*.g.cs", GENERATED, None,
        "the map, registry, typed contracts and embedded provenance, from merge(package, overlay)"),
    Row("tests/{name}.Tests/Generated/*.g.cs", GENERATED, None,
        "the correspondence and provenance tests, from the same merge"),
    Row("corpus/*", GENERATED, None,
        "the corpus copy intake proved against the map's baseline"),
    Row("backlog/*.md", GENERATED, None,
        "the entries still to build, from the merge; GitHub issues are synced from it"),
    Row("scripts/validate.sh", GENERATED, None, "the gate recipe (M3): the factory's definition of acceptable"),
    Row("scripts/map-overlay.py", GENERATED, None, "the gate recipe: 0015's merge"),
    Row("scripts/engine-gate.py", GENERATED, None, "the gate recipe: its non-dotnet checks"),
    Row("scripts/factory/*.py", GENERATED, None, "the factory's generator, vendored so the gate can regenerate"),
    Row(".github/workflows/validate.yml", GENERATED, None, "the gate recipe: CI runs validate.sh full"),
    Row("global.json", MANAGED, 1,
        "the kernel's SDK pin and roll-forward policy; an engine that must move it adopts it"),
    Row("NuGet.config", MANAGED, 2,
        "package sources and source mapping: supply-chain policy; an extra feed is an adoption"),
    Row("Directory.Build.props", MANAGED, 2,
        "target frameworks, analyzers, warnings-as-errors, determinism and lock-file policy"),
    Row("Directory.Packages.props", ENGINE_OWNED, None,
        "central package management and the test packages an engine bumps; imports the generated pins"),
    Row("{name}.slnx", ENGINE_OWNED, None, "the engine adds projects to its solution"),
    Row("src/{name}/{name}.csproj", ENGINE_OWNED, None, "the engine adds references and files"),
    Row("tests/{name}.Tests/{name}.Tests.csproj", ENGINE_OWNED, None, "the engine adds test references"),
    Row("corpus-map.overlay.json", ENGINE_OWNED, None, "the engine's three fields per entry (0015)"),
    Row("src/{name}/packages.lock.json", ENGINE_OWNED, None,
        "written by verify's first restore when absent, then reviewed, committed and relocked by the engine"),
    Row("tests/{name}.Tests/packages.lock.json", ENGINE_OWNED, None, "the same, for the test project"),
)

# Every version of every managed recipe: path -> {recipe version: SHA-256 of the bytes it wrote}.
# Version 1 of each is what the write-once scaffold wrote before #72. Never remove a version: an
# engine still carrying those bytes is unedited, and is migrated rather than refused.
RECIPE_SHA256 = {
    "global.json": {
        1: "12f1cf1c3eef038f55de570dc8f5e321f4ff5306a9281106c43cc60a1f78a371",
    },
    "NuGet.config": {
        1: "b6475c7eb5334ba07f88ad900e82da0ebda9f269733c1c09237a72796c8d77f2",
        2: "e53f00efe0e550fb452b2e1d8d3b1e2f0cdd1de86628eff7d60a813ebfa1818f",
    },
    "Directory.Build.props": {
        1: "1392b57192cfe16ac70aa847f932c52f136765c9ce60ed94254d73dafd0d14ef",
        2: "73c373b1457e4149eb7ab7da1aed49314536ca8945dea8022c1efbd49c7a1a8f",
    },
}


class OwnershipError(Exception):
    """A managed file cannot be written without discarding an edit, or a flag names no managed file."""


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def rows(name):
    """TABLE with `{name}` replaced by the engine name."""
    return tuple(row._replace(pattern=row.pattern.replace("{name}", name)) for row in TABLE)


def _matches(pattern, relative):
    wanted, parts = pattern.split("/"), relative.split("/")
    return len(wanted) == len(parts) and all(fnmatch.fnmatchcase(p, w) for p, w in zip(parts, wanted))


def matching(relative, name):
    """Every row of the table that `relative` (an engine-relative POSIX path) matches."""
    return [row for row in rows(name) if _matches(row.pattern, relative)]


def classify(relative, name):
    """The one row `relative` matches, or None when it matches none. More than one is a table bug."""
    found = matching(relative, name)
    if len(found) > 1:
        raise OwnershipError(f"{relative} matches {len(found)} rows of the ownership table "
                             f"({', '.join(r.pattern for r in found)}); it must match exactly one")
    return found[0] if found else None


def managed_rows(name):
    return [row for row in rows(name) if row.cls == MANAGED]


def adopted(out):
    """Managed paths the engine's provenance.json records as adopted (engine-owned).

    An unreadable or absent record adopts nothing. That is the safe direction: an adopted file
    that has been edited is then refused, naming --adopt, rather than overwritten.
    """
    try:
        with open(os.path.join(out, PROVENANCE), encoding="utf-8") as handle:
            record = json.load(handle)
        items = record.get("engineOwned") or []
        return {item["path"] for item in items if isinstance(item, dict) and item.get("adopted") is True
                and isinstance(item.get("path"), str)}
    except (OSError, ValueError, AttributeError, TypeError, KeyError):
        return set()


def plan_managed(out, name, recipes, adopt=(), reset=()):
    """Decide every managed file for a run into `out`.

    `recipes` maps each managed path to the current recipe's bytes. Returns (writes, managed,
    adopted_now, notes): the bytes to write per path, {path: recipe version} for the files that
    stay managed, the set that is engine-owned by adoption, and a line per decision worth
    logging. Raises OwnershipError, before anything is written, for a flag that names no managed
    file and for every hand-edited managed file neither flag settles.
    """
    table = {row.pattern: row for row in managed_rows(name)}
    if set(recipes) != set(table):
        raise OwnershipError(f"the managed recipes ({sorted(recipes)}) are not the managed rows of the "
                             f"ownership table ({sorted(table)})")
    unknown = sorted(p for p in set(adopt) | set(reset) if p not in table)
    if unknown:
        raise OwnershipError(f"--adopt and --reset name managed files only ({', '.join(sorted(table))}); "
                             f"{', '.join(unknown)} is not one")
    both = sorted(set(adopt) & set(reset))
    if both:
        raise OwnershipError(f"{', '.join(both)} is given to both --adopt and --reset")
    recorded = adopted(out)
    writes, managed, adopted_now, notes, refused = {}, {}, set(), [], []
    for path, row in sorted(table.items()):
        target = os.path.join(out, *path.split("/"))
        current = recipes[path]
        if sha256(current) != RECIPE_SHA256.get(path, {}).get(row.recipe):
            raise OwnershipError(f"the {path} recipe's bytes are not recipe version {row.recipe}'s recorded "
                                 f"hash; a changed recipe needs a new version in the ownership table")
        on_disk = None
        if os.path.isfile(target):
            with open(target, "rb") as handle:
                on_disk = handle.read()
        if path in reset:
            writes[path] = current
            managed[path] = row.recipe
            notes.append(f"reset {path} to managed recipe {row.recipe}")
        elif path in adopt or path in recorded:
            adopted_now.add(path)
            if on_disk is None:
                writes[path] = current
            if path in adopt and path not in recorded:
                notes.append(f"adopted {path}: engine-owned from now on")
        elif on_disk is None:
            writes[path] = current
            managed[path] = row.recipe
        else:
            versions = [v for v, digest in RECIPE_SHA256[path].items() if digest == sha256(on_disk)]
            if not versions:
                refused.append(path)
                continue
            managed[path] = row.recipe
            if on_disk != current:
                writes[path] = current
                notes.append(f"updated managed {path} from recipe {max(versions)} to {row.recipe}")
    if refused:
        raise OwnershipError(
            f"{', '.join(refused)} {'is a managed file' if len(refused) == 1 else 'are managed files'} "
            f"edited by hand: the bytes are no version of the factory's recipe, so produce will neither "
            f"overwrite the edit nor leave a stale policy unnoticed. Pass --adopt <path> to make it the "
            f"engine's own from now on, or --reset <path> to replace it with the current recipe")
    return writes, managed, adopted_now, notes
