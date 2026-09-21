#!/usr/bin/env python3
"""Run this repository's gate, and be able to say which of its checks a change owes (#342).

`scripts/validate.sh` was the one definition of "acceptable", and it was all-or-nothing: every
corpus, every package, every test, on every invocation. That default is right and it is kept --
`--full` runs exactly the steps that script ran, in the same order, with the same verdicts, and
`scripts/validate.sh` is now a wrapper over it so that every caller that existed keeps working.

What the script had no vocabulary for is a narrower question that is nonetheless a real one:

  * `--release <map>` -- a map is being tagged. Every structural and corpus check is owed,
    because a map is certified against the whole repository's rules and not its own. Packing the
    other three maps is not owed: they are not what is being published, and their packages are
    gated on every pull request already.
  * `--changed --base <sha>` -- a pull request. The tests and the repository-wide checks are
    always owed, because they are what says the checkers still work and the documents are still
    true. A map fixture proves something about its own map and nothing about another's.

Scoping a gate is how a gate stops examining things, so the rules here are built to fail towards
running more:

  * The scope is decided by three tables of paths -- CORE_PREFIXES, CORE_FILES and
    FACTORY_PREFIXES -- and every row of each is covered by a test.
  * A path that matches no row widens to `full`. So does a missing base SHA, an unreadable diff,
    and any exception raised while classifying. There is no input for which "run less" is the
    accidental answer.
  * `full` is not a computed scope. It is the literal list of steps, with every map, and it is
    what runs unless something asked otherwise and succeeded in saying so.
  * A step that a scope narrows says so on its own line, with what it ran and what it did not.
    A skipped check that prints nothing is indistinguishable from a passing one.
  * A map the globs find and this file does not know about fails the run. The per-map locator
    invocations cannot be derived -- three corpora, three grammars -- so they are written down,
    and a written-down list that silently misses a map is the defect this file exists to refuse.

Usage:
  validate-repo.py [--full]                 every check, every map -- the default
  validate-repo.py --changed --base <sha>   the checks a diff against <sha> could have broken
  validate-repo.py --release <map>          every check; package only examples/<map>
  validate-repo.py --explain --base <sha>   print the scope and the reason for it, run nothing

Exit 0 when every step that ran passed, 1 when one did not, 2 on a usage error.
"""
from __future__ import annotations

import argparse
import dataclasses
import glob
import hashlib
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent

# The two globs scripts/validate.sh read, in its order. Two and not one: a map that reconciles
# another cannot sit beside it while both are maps, because pack-map.py requires exactly one
# corpus-map*.json in a packable directory. No map is one level down today; the glob stays
# because the next reconciliation needs it and an unglobbed map would be an unchecked one.
MAP_GLOBS = ("examples/*/corpus-map*.json", "examples/*/*/corpus-map*.json")
STAGING_GLOB = "examples/*/*/staged-inputs.json"
PACKAGE_GLOB = "examples/*/map-package.json"


@dataclasses.dataclass(frozen=True)
class Fixture:
    """One map, and everything in this repository that is about that map and no other."""

    map: str
    # The directory a change is attributed to. Usually the map's own, but a map may be a second
    # slice of a corpus committed under another trial, and then a change to that corpus is a
    # change to this map too.
    corpora: tuple[str, ...]
    # The locator invocation(s) for this map. A citation is a promise, and three grammars check
    # three kinds of promise: page markers over a Gutenberg text, containment in the section tree
    # of eCFR XML, and page markers over PDF-extracted text. None generalises to the others, so
    # the argv is written per map rather than derived.
    locators: tuple[tuple[str, ...], ...]

    @property
    def directory(self) -> str:
        return os.path.dirname(self.map)


ECFR = "examples/faa-part-107/check-locators-section.py"
PDF_TEXT = "examples/srd-52-combat/check-locators-pdf-text.py"
# The mapper's entry point, as a script rather than as the directory `tools/mapper`.
#
# Both run the same file. The difference is bytecode: executing a directory makes Python *import*
# `__main__`, which caches tools/mapper/__pycache__/__main__.cpython-312.pyc before the first line
# of it runs -- so the `sys.dont_write_bytecode` inside cannot prevent its own caching, and the
# gate's last step rightly failed on it the first time it could see (#384). A file path is run as
# `__main__` from disk and cached nowhere. sys.path[0] is tools/mapper either way, and the entry
# point computes the path it inserts from `__file__`, so nothing else changes.
#
# `python3 tools/mapper <command>` stays the documented form -- docs/mapper.md and several
# committed evidence artifacts name it -- and it still writes that one ignored file, which no code
# in the file can stop. What is fixed here is the gate, which is what promises to leave the
# checkout as it found it.
MAPPER = "tools/mapper/__main__.py"

# Every map this repository holds, with the corpus directories it reads and the citation grammar
# that checks it. `check_fixtures_cover_every_map` holds this table to the globs above: a map
# added without a row here fails the run rather than going unchecked.
FIXTURES = (
    Fixture(
        map="examples/hoyle-backgammon/corpus-map.json",
        corpora=("examples/hoyle-backgammon",),
        locators=((
            "tools/check-locators.py",
            "examples/hoyle-backgammon/corpus-map.json",
            "examples/hoyle-backgammon/hoyle.txt",
        ),),
    ),
    Fixture(
        map="examples/faa-part-107/corpus-map.json",
        corpora=("examples/faa-part-107",),
        locators=((
            ECFR,
            "examples/faa-part-107/corpus-map.json",
            "examples/faa-part-107/part107.xml",
        ),),
    ),
    Fixture(
        map="examples/faa-part-107-temporal/corpus-map-2020-01-01.json",
        corpora=("examples/faa-part-107-temporal",),
        locators=((
            ECFR,
            "examples/faa-part-107-temporal/corpus-map-2020-01-01.json",
            "examples/faa-part-107-temporal/part107-2020-01-01.xml",
        ),),
    ),
    # A third corpus through the same eCFR checker, and a different title of the CFR: trial 9's
    # § 1.121-1, as the blind second mapping reconciled it (0014's Map C, promoted to be the map
    # under #8). It cites a worked example -- `§ 1.121-1(b)(4) Example 4` -- which the grammar
    # could not read until that mapping found the rule inside one. The checker is reused and not
    # copied, which is the point: the grammar is the grammar.
    #
    # build-map-c.py --check is here and not elsewhere because the map above is what it builds
    # from the first mapping plus the adjudication record: a change to one and not the other is a
    # correction nobody ruled on. The first mapping is frozen evidence at
    # blind-mapping/first-map.json and is checked nowhere else, which this covers -- its bytes
    # cannot change without the map they build stopping matching.
    Fixture(
        map="examples/tax-121-principal-residence/corpus-map.json",
        corpora=("examples/tax-121-principal-residence",),
        locators=(
            (
                ECFR,
                "examples/tax-121-principal-residence/corpus-map.json",
                "examples/tax-121-principal-residence/section-1.121-1.xml",
            ),
            (
                "examples/tax-121-principal-residence/blind-mapping/build-map-c.py",
                "--check",
            ),
        ),
    ),
    # A fourth corpus through the same eCFR checker, and the first map that cites two of them
    # (0039, 0042): trial 10's § 172.101 and § 172.102, whose rules cross a served-document
    # boundary. Every corpus a map cites names the sourceId its entries cite, because a single
    # positional argument cannot say which of two documents a citation belongs to.
    Fixture(
        map="examples/hazmat-172-table/corpus-map.json",
        corpora=("examples/hazmat-172-table",),
        locators=((
            ECFR,
            "examples/hazmat-172-table/corpus-map.json",
            "cfr-49-172.101=examples/hazmat-172-table/section-172.101.xml",
            "cfr-49-172.102=examples/hazmat-172-table/section-172.102.xml",
        ),),
    ),
    # A third grammar: page markers over text extracted from a PDF. extract.py first holds the
    # committed text to the manifest's contentHash and the committed PDF to sourcePdf.sha256, and
    # re-derives the text from the PDF where the pinned pdftotext is installed (NOT VERIFIED,
    # printed, where it is not). The locator checker then holds each quote to the text.
    Fixture(
        map="examples/srd-52-combat/corpus-map.json",
        corpora=("examples/srd-52-combat",),
        locators=(
            ("examples/srd-52-combat/extract.py", "--check"),
            (
                PDF_TEXT,
                "examples/srd-52-combat/corpus-map.json",
                "examples/srd-52-combat/srd-5.2.1.txt",
            ),
        ),
    ),
    # A second slice of the same corpus. The checker and the text stay where they were committed:
    # the conditions map declares its own manifest and points `committedPath` at that one copy,
    # because a 6 MB PDF and a 1.4 MB text duplicated per slice would be a second baseline to keep
    # in step, not a second corpus. So this map's corpora include the combat trial's directory: a
    # change there is a change to this map, and `--changed` has to check it.
    Fixture(
        map="examples/srd-52-conditions/corpus-map.json",
        corpora=("examples/srd-52-conditions", "examples/srd-52-combat"),
        locators=((
            PDF_TEXT,
            "examples/srd-52-conditions/corpus-map.json",
            "examples/srd-52-combat/srd-5.2.1.txt",
        ),),
    ),
)


def discover_maps(root: pathlib.Path = ROOT) -> list[str]:
    """Every corpus map, by the globs and in the order scripts/validate.sh read them."""
    found: list[str] = []
    for pattern in MAP_GLOBS:
        found.extend(discover(root, pattern))
    return found


def discover(root: pathlib.Path, pattern: str) -> list[str]:
    """Paths matching `pattern`, in the order a shell glob would have listed them.

    The key is the path split on "/" so that `faa-part-107` sorts before `faa-part-107-temporal`,
    the way the glob in scripts/validate.sh did. Sorting the strings instead puts the longer one
    first, because "-" is below "/" in ASCII, and the steps would report the maps in an order no
    reader of the old output would recognise.
    """
    paths = [str(pathlib.Path(p).relative_to(root)) for p in glob.glob(str(root / pattern))]
    return sorted(paths, key=lambda p: p.split("/"))


# --------------------------------------------------------------------------------------------
# What a change owes
# --------------------------------------------------------------------------------------------

# The contract, the two subsystems that read and write maps, the packer, and the locator
# grammars. A change to any of these can change the verdict on a map it does not mention, so
# there is no narrower honest answer than every map. The locator checkers live under
# examples/ because each was written for a corpus and then reused across corpora; that is where
# they are, and it is why these rows are matched before the examples/<map>/ row below.
CORE_PREFIXES = (
    "tools/mapcontract/",
    "tools/mapvalidator/",
    "tools/mapper/",
    "schema/",
)
CORE_FILES = (
    "tools/pack-map.py",
    "tools/check-map.py",
    "tools/build-check-map.py",
    "tools/check-locators.py",
    "tools/check-map-review.py",
    "tools/mutate-map.py",
    ECFR,
    PDF_TEXT,
    "examples/srd-52-combat/extract.py",
    "examples/tax-121-principal-residence/blind-mapping/build-map-c.py",
    # The gate itself. A change to what decides the scope is judged at the widest scope, by the
    # scope it is replacing, because it cannot be trusted to narrow its own review.
    "tools/validate-repo.py",
    "scripts/validate.sh",
)
FACTORY_PREFIXES = ("tools/factory/", "scripts/validate-engine.sh", "tools/validate-engine.py")

# The map tools/validate-engine.py produces its engine from. Declared here because the scope has
# to know whether a diff owes that job, and held to the source by the tests rather than trusted.
ENGINE_MAP = "examples/hoyle-backgammon"


@dataclasses.dataclass(frozen=True)
class Scope:
    """Which steps run, over which maps, and the reason -- one line per path that decided it."""

    name: str
    maps: tuple[str, ...]
    packages: tuple[str, ...]
    engine: bool
    reasons: tuple[str, ...]

    @property
    def is_full(self) -> bool:
        return self.name == "full"


def full_scope(root: pathlib.Path = ROOT, reason: str = "asked for every check") -> Scope:
    return Scope(
        name="full",
        maps=tuple(discover_maps(root)),
        packages=tuple(discover(root, PACKAGE_GLOB)),
        engine=True,
        reasons=(reason,),
    )


def _fixtures_for(directory: str) -> list[Fixture]:
    """Every map a change under `directory` could have broken.

    A map's own directory, and any corpus directory it reads. srd-52-conditions cites the text
    committed under srd-52-combat, so a change there is a change to both maps; deriving that from
    the map's own path would have missed it.
    """
    return [f for f in FIXTURES if directory in f.corpora]


def classify(paths, root: pathlib.Path = ROOT) -> Scope:
    """The scope a set of changed paths owes. Widens to full on anything it cannot place."""
    paths = [p.strip() for p in paths if p.strip()]
    if not paths:
        return full_scope(root, "the diff named no paths")

    maps: list[str] = []
    packages: list[str] = []
    engine = False
    reasons: list[str] = []

    def widen(path: str, why: str) -> Scope:
        return full_scope(root, f"{path}: {why}")

    for path in sorted(set(paths)):
        if path.startswith(CORE_PREFIXES) or path in CORE_FILES:
            return widen(path, "the map contract, a subsystem over it, or a citation grammar")
        if path.startswith(FACTORY_PREFIXES):
            engine = True
            reasons.append(f"{path}: the factory -- its tests, and an engine produced from scratch")
            continue
        parts = path.split("/")
        if parts[0] == "examples" and len(parts) > 2:
            directory = "/".join(parts[:2])
            affected = _fixtures_for(directory)
            if not affected:
                # An examples/ directory with no map: validator-attack, blind-mapping-trial,
                # hoyle-blind-rebuild. Each is evidence some step reads, and none of them is a
                # map fixture this can narrow to, so the honest answer is every check.
                return widen(path, f"{directory} is not a map fixture this file knows how to scope")
            for fixture in affected:
                if fixture.map not in maps:
                    maps.append(fixture.map)
                    reasons.append(f"{path}: {fixture.map}")
                settings = os.path.join(fixture.directory, "map-package.json")
                if (root / settings).exists() and settings not in packages:
                    packages.append(settings)
            continue
        return widen(path, "no rule places this path, so every check is owed")

    if not maps and not engine:
        return widen(paths[0], "nothing in the diff narrowed the scope")
    if packages:
        # An engine is produced from a packable map, so a change to one owes the engine job the
        # same way a change to the factory does. tools/validate-engine.py produces from
        # ENGINE_MAP and reads every examples/*/map-package.json;
        # `test_the_engine_is_owed_by_the_map_it_is_produced_from` holds this claim to that file.
        engine = True
        reasons.append("a packable map changed: an engine is produced from one")
    order = discover_maps(root)
    return Scope(
        name="changed",
        maps=tuple(m for m in order if m in maps),
        packages=tuple(p for p in discover(root, PACKAGE_GLOB) if p in packages),
        engine=engine,
        reasons=tuple(reasons),
    )


def classify_diff(base: str, root: pathlib.Path = ROOT) -> Scope:
    """`classify` over `git diff --name-only <base>...HEAD`. Any failure reading it is full."""
    if not base:
        return full_scope(root, "no base commit was given")
    try:
        out = subprocess.run(
            ["git", "diff", "--name-only", f"{base}...HEAD"],
            cwd=root, capture_output=True, text=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, OSError) as exc:
        return full_scope(root, f"the diff against {base} could not be read ({exc})")
    try:
        return classify(out.splitlines(), root)
    except Exception as exc:  # noqa: BLE001 -- a classifier that raises must not skip a check
        return full_scope(root, f"classifying the diff raised {exc!r}")


def release_scope(name: str, root: pathlib.Path = ROOT) -> Scope:
    """Every structural and corpus check, and only the tagged map's package.

    A map is certified against this repository's rules and not its own, so nothing structural is
    narrowed here. What is narrowed is packing: three packages that are not being published are
    gated on every pull request already, and repeating them on the tag proves nothing about the
    tag.
    """
    directory = name if name.startswith("examples/") else f"examples/{name}"
    settings = os.path.join(directory, "map-package.json")
    if not (root / settings).exists():
        raise SystemExit(f"validate-repo.py: {settings} does not exist -- no such packable map")
    return Scope(
        name="release",
        maps=tuple(discover_maps(root)),
        packages=(settings,),
        engine=True,
        reasons=(f"releasing {directory}: every check, and only this map is packed",),
    )


# --------------------------------------------------------------------------------------------
# The steps
# --------------------------------------------------------------------------------------------
#
# Every step below either proves something or says it could not. A step that reports ok while
# examining nothing is the defect this project has found in its own tools twice, so each step
# that iterates over inputs counts them and fails on zero -- except where a scope narrowed the
# inputs away deliberately, which is printed as a skip and never reached under --full.


class Run:
    """One invocation of the gate: where it runs, what it has printed, and what it found."""

    def __init__(self, root: pathlib.Path, scope: Scope, with_evidence: bool = False):
        self.root = root
        self.scope = scope
        # Verify the evidence wherever it lives, fetching what is not in this checkout, rather
        # than reading it from beside the checkers (#349).
        self.with_evidence = with_evidence
        self.failed = False
        self.step = 0

    def python(self, *argv: str, accept=(0,)) -> bool:
        proc = subprocess.run([sys.executable, *argv], cwd=self.root)
        return proc.returncode in accept

    def quiet(self, *argv: str):
        return subprocess.run([sys.executable, *argv], cwd=self.root,
                              capture_output=True, text=True)

    def skip(self, what: str) -> bool:
        """A step a narrower scope did not ask for. Never reachable under --full."""
        if self.scope.is_full:
            raise AssertionError(f"--full skipped {what} -- full is not allowed to skip anything")
        print(f"not owed by this change: {what}")
        return True

    def run(self, what: str, fn) -> None:
        self.step += 1
        print(f"\n==> [{self.step}] {what}")
        try:
            ok = fn()
        except AssertionError:
            raise
        except Exception as exc:  # noqa: BLE001
            print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
            ok = False
        print(f"{'ok  ' if ok else 'FAIL'} {what}")
        if not ok:
            self.failed = True


def _manifest_for(root: pathlib.Path, map_path: str) -> list[str]:
    """check-map.py finds a corpus-manifest.json beside the map by itself.

    A map in a subdirectory has its corpus one level up, and without this its manifest, posture
    and reference checks would all report NOT VERIFIED -- a step examining nothing.
    """
    directory = pathlib.Path(map_path).parent
    if not (root / directory / "corpus-manifest.json").exists():
        beside = directory.parent / "corpus-manifest.json"
        if (root / beside).exists():
            return ["--manifest", str(beside)]
    return []


def _over_maps(run: Run, noun: str, invoke, empty: str):
    """Run `invoke` for each map in scope, printing the map and counting what was examined."""
    checked = 0
    for map_path in run.scope.maps:
        print(f"--- {map_path}")
        if not invoke(map_path):
            return False
        checked += 1
    if checked == 0:
        if not run.scope.is_full:
            return run.skip(empty)
        print("no corpus maps found -- this step proved nothing", file=sys.stderr)
        return False
    print(f"{checked} {noun}")
    return True


def step_boundaries(run: Run) -> bool:
    """Mapping, map validation and engine generation are three sibling subsystems over one map
    contract, and none of them may import another (0032). An import is one line and the reason
    not to write it is invisible at the moment someone does, so the direction is declared in the
    checker and held here rather than hoped for. First, because it is a fact about the sources
    every step below reads."""
    return run.python("tools/check-boundaries.py")


def step_built_checker(run: Run) -> bool:
    """check-map.py ships as one file inside every map package, so it is built from the two
    packages rather than edited (#74). A module changed without rebuilding would ship, and be
    judged by, the checks as they were; every step after this one runs the built file."""
    return run.python("tools/build-check-map.py", "--check")


def step_schema(run: Run) -> bool:
    """Every map, against the schema its own specification describes."""
    return _over_maps(
        run, "map(s) checked",
        lambda m: run.python("tools/check-map.py", m, *_manifest_for(run.root, m)),
        "any map's schema check",
    )


def step_protocols(run: Run) -> bool:
    """Every map says how its corpus communicates rules, and the protocol is one this mapper can
    act on (0032, #249). A map with no protocol is one that cannot say how it was read: each
    trial decided that by hand and recorded nothing, which is how a phrase list went on being the
    interrogation mechanism for a corpus that points by naming its terms (#208)."""
    return _over_maps(
        run, "protocol(s) checked",
        lambda m: run.python(MAPPER, "protocol", m),
        "any map's protocol",
    )


def step_pointers(run: Run) -> bool:
    """The interrogation each protocol obliges, for the mechanisms this subsystem detects. A
    corpus that declares `defined-term-use` and on which nothing fires fails: a silent zero is the
    shape 0026 already refuses for phrases, and it is exactly what #208 measured for this corpus
    under the phrase list -- 0 detected in passages holding 51 references.

    A naming with no declaration is a failure, not a NOT VERIFIED. This step accepted 3 while
    #254 was open, because whether a `scope: out`, `status: declined` entry owed the declaration
    was a question about the corpus that the tool was right not to answer. 0058 answers it -- the
    passage that points declares it, whatever the engine does with the rule -- so a naming the map
    leaves undeclared is now a defect the gate names."""
    return _over_maps(
        run, "map(s) interrogated",
        lambda m: run.python(MAPPER, "pointers", m),
        "any map's pointer interrogation",
    )


def step_inventory(run: Run) -> bool:
    """What each map's extent claims, against what its walk reached (#255). `extent` says how much
    of the corpus a map read, and until this step nothing evidenced it: the locator checkers'
    coverage asks only whether every page or section of the extent is touched by some quote, which
    a map satisfies by reaching one sentence on a page.

    3 is the expected outcome on every committed map today: each was walked before anything
    measured the walk, and the counts are #267. A map that enumerates no unit at all, or one no
    entry's quote is found in, exits 1 here -- an inventory of nothing has nothing unaccounted."""
    return _over_maps(
        run, "map(s) inventoried",
        lambda m: run.python(MAPPER, "inventory", m, accept=(0, 3)),
        "any map's inventory",
    )


def step_sweeps(run: Run) -> bool:
    """The completeness challenge each protocol requires, run over the units the walk left
    unaccounted (#250). Each sweep asks whether an unaccounted unit looks like it states a rule of
    its kind, which is a recall device over a bounded pile and not the corpus-wide phrase scan
    #208 measured as blind.

    What exits 1 is a sweep the protocol requires that fired on no unaccounted unit *and* on no
    unit the walk reached. A required sweep the registry does not implement is reported by name
    and exits 3; it is never skipped."""
    return _over_maps(
        run, "map(s) swept",
        lambda m: run.python(MAPPER, "sweeps", m, accept=(0, 3)),
        "any map's required sweeps",
    )


def step_map_reviews(run: Run) -> bool:
    """Every map carries a review of its exact bytes (0017): a blind second mapping, a verdict
    from a separate context, or an exemption that says why. The checker counts the maps it
    examined and fails on none, and prints every exemption, so neither an empty glob nor a waiver
    passes quietly. It reads every map whatever the scope: a review is a fact about the set."""
    return run.python("tools/check-map-review.py")


def step_blind_staging(run: Run) -> bool:
    """What a blind second mapping was given is recorded by digest beside the comparison, and the
    staged documents are the redacted ones (#223). The comparison tooling compares two maps and
    cannot see the inputs, so a contaminated run reported as blind manufactures agreement -- which
    is the evidence the whole procedure produces. `mapper stage --verify` re-hashes every file a
    record names and re-runs the leak scan over the staged documents, so neither a swapped input
    nor a record that claims a redaction it did not make passes."""
    directories = {os.path.dirname(m) for m in run.scope.maps}
    records = [r for r in discover(run.root, STAGING_GLOB)
               if os.path.dirname(os.path.dirname(r)) in directories]
    checked = 0
    for record in records:
        print(f"--- {record}")
        if not run.python(MAPPER, "stage", "--verify", record):
            return False
        checked += 1
    if checked == 0:
        if not run.scope.is_full:
            return run.skip("any blind-mapping staging record")
        print("no blind-mapping staging record found -- this step proved nothing", file=sys.stderr)
        return False
    print(f"{checked} staged blind input(s) verified")
    return True


def step_locators(run: Run) -> bool:
    """A citation is a promise. Three grammars, three checkers: page markers for a Gutenberg text,
    containment in the section tree for eCFR XML, and page markers over PDF-extracted text held
    exactly. None generalises to the others, and pointing one at the wrong corpus exits 2 rather
    than passing. The invocations are FIXTURES above, one row per map."""
    by_map = {f.map: f for f in FIXTURES}
    checked = 0
    for map_path in run.scope.maps:
        fixture = by_map.get(map_path)
        if fixture is None:
            print(f"  X  {map_path} has no row in FIXTURES -- its citations are checked by nothing",
                  file=sys.stderr)
            return False
        for argv in fixture.locators:
            if not run.python(*argv):
                return False
        checked += 1
    if checked == 0:
        if not run.scope.is_full:
            return run.skip("any map's citations")
        print("no corpus maps found -- this step proved nothing", file=sys.stderr)
        return False
    print(f"{checked} map(s) whose citations resolve")
    return True


def step_fixture_table(run: Run) -> bool:
    """Every map the globs find has a row in FIXTURES, and every row names a map that exists.

    FIXTURES is the only hand-written list of inputs here, so it is the only one that can go
    stale. A map added without a row would have no citation check and no corpus attribution, and
    would be narrowed away by --changed without anybody noticing; a row for a map that was moved
    would point a grammar at nothing. Both fail here, under --full and under every narrower scope,
    because the table is a fact about the repository and not about the change."""
    on_disk = set(discover_maps(run.root))
    declared = {f.map for f in FIXTURES}
    bad = False
    for missing in sorted(on_disk - declared):
        print(f"  X  {missing} is a map with no row in tools/validate-repo.py FIXTURES")
        bad = True
    for phantom in sorted(declared - on_disk):
        print(f"  X  FIXTURES names {phantom}, which is not a map in this checkout")
        bad = True
    for fixture in FIXTURES:
        for corpus in fixture.corpora:
            if not (run.root / corpus).is_dir():
                print(f"  X  {fixture.map} names corpus directory {corpus}, which does not exist")
                bad = True
    if not on_disk:
        print("no corpus maps found -- this check proved nothing", file=sys.stderr)
        return False
    if bad:
        return False
    print(f"{len(on_disk)} map(s), each with a row that names its corpora and its grammar")
    return True


def step_evidence(run: Run) -> bool:
    """Every artifact under examples/ is in the lock, and its bytes are what the lock says (#349).

    A corpus is pinned by its manifest's `contentHash`, a staged blind input by its record's
    digests, trial 9's first mapping by `build-map-c.py --check`. The evidence no check reads was
    pinned by nothing at all -- 42 files and 892 KB whose bytes could change with no run noticing.
    The lock covers all 189, in both directions, so evidence added beside it is a failure rather
    than a file the lock happens not to mention.

    It runs at every scope. What it holds is a fact about the tree, not about the change, and it
    takes 40 milliseconds over 15.5 MB.

    With --with-evidence the same artifacts are verified through tools/fetch-evidence.py, which
    reads each one wherever the lock says it lives -- this repository today, a content-addressed
    archive if one is ever named."""
    if run.with_evidence:
        return run.python("tools/fetch-evidence.py", "--verify")
    return run.python("tools/check-evidence.py")


def step_validator_attack(run: Run) -> bool:
    """The validator, attacked with a damaged map. Every check has been watched failing on a unit
    fixture; that proves each fires, not how much of a real error reaches the gate.
    tools/mutate-map.py damages a committed map one named way at a time and measures what is
    refused (#259, examples/validator-attack/). The measurement is committed, and this re-runs it
    and fails when a row moves -- a check that grew, a map that was corrected, or a mutation that
    stopped landing. No committed map is written to: each run works on a copy in a temporary
    directory.

    It runs at every scope. It measures the validator rather than any one map, and a change that
    moves a row is one nobody chose to make."""
    return run.python("tools/mutate-map.py", "--check", "examples/validator-attack/results.json")


def step_map_packages(run: Run) -> bool:
    """Every map that declares a package version passes the gate its publish workflow runs, and
    packs to the same bytes twice (0015). A map that could not be published is found here, on the
    pull request, rather than on the tag -- after the version number was already chosen.

    Under --release only the tagged map is packed: the others are gated on every pull request,
    and packing them again proves nothing about the tag."""
    out = pathlib.Path(tempfile.mkdtemp())
    try:
        packed = 0
        for settings in run.scope.packages:
            directory = os.path.dirname(settings)
            print(f"--- {directory}")
            first = run.quiet("tools/pack-map.py", directory, "--out", str(out / "a"))
            if first.returncode != 0:
                sys.stdout.write(first.stdout)
                sys.stderr.write(first.stderr)
                return False
            tail = first.stdout.rstrip().splitlines()
            if tail:
                print(tail[-1])
            second = run.quiet("tools/pack-map.py", directory, "--out", str(out / "b"))
            if second.returncode != 0:
                sys.stdout.write(second.stdout)
                sys.stderr.write(second.stderr)
                return False
            packed += 1
        if packed == 0:
            if not run.scope.is_full:
                return run.skip("packing any map")
            print("no map declares map-package.json -- this step proved nothing", file=sys.stderr)
            return False
        a = _digests(out / "a")
        b = _digests(out / "b")
        if a != b:
            print(f"two packs of the same inputs differ:\n{a}\n{b}", file=sys.stderr)
            return False
        print(f"{packed} map package(s) gated and packed, byte-identical twice")
        return True
    finally:
        shutil.rmtree(out, ignore_errors=True)


def _digests(directory: pathlib.Path) -> list[str]:
    return sorted(
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}"
        for p in directory.glob("*.nupkg")
    )


def step_tool_tests(run: Run) -> bool:
    """The checkers' own tests, laid out by subsystem (0033): tools/tests/mapper/,
    tools/tests/mapvalidator/, tools/tests/factory/, and at the top level the tests of the
    checkers that hold *this repository* to its word rather than any subsystem. A checker nobody
    has watched fail is not yet a checker, and this repo has shipped two that counted work they
    had not done.

    Every scope runs every test. They are what says the checkers still work, and which of them
    a diff could have broken is not a question a path table can answer honestly.

    The suite is distributed over the cores the machine has (#344). `-n auto` reads the process
    CPU affinity, so it is four on a GitHub runner and whatever a developer's machine gives.
    Nothing is skipped or reordered away by that -- but a distributed run can lose a worker in a
    way a serial one cannot, and "1400 passed" reads exactly like "1750 passed" to a grep. So the
    suite is collected first and the run is held to the count: a run that passed fewer tests than
    were collected fails, whatever pytest's own exit code said.
    """
    # `-p no:cacheprovider` keeps .pytest_cache out; the env keeps __pycache__ out of every test
    # module pytest imports. It is set here and not for the whole gate (#384) so that a *checker*
    # which writes bytecode is caught by the last step rather than hidden by the run's
    # environment. xdist's workers are child processes, so they inherit it.
    bare = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    collected = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "tools/tests", "-q",
         "--collect-only"],
        cwd=run.root, capture_output=True, text=True, env=bare,
    )
    if collected.returncode != 0:
        sys.stdout.write(collected.stdout)
        sys.stderr.write(collected.stderr)
        print("the suite could not be collected -- nothing was proven", file=sys.stderr)
        return False
    wanted = _count(collected.stdout, r"(\d+) tests? collected")
    if not wanted:
        print("collection reported no tests -- nothing was proven", file=sys.stderr)
        return False

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "tools/tests", "-q",
         "-n", "auto"],
        cwd=run.root, capture_output=True, text=True, env=bare,
    )
    if proc.returncode != 0:
        sys.stdout.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        return False
    lines = proc.stdout.rstrip().splitlines()
    if lines:
        print(lines[-1])
    # A green pytest run over an empty suite is the same lie as a check with no inputs, and a
    # distributed run that lost a worker is the same lie with a plausible number on it. So every
    # collected test must be accounted for by one of pytest's own outcome counters.
    #
    # A skip is an outcome, so it accounts for a test -- and it is never absorbed silently. This
    # job has no .NET SDK, so the tests that need one skip here and the `engine` job runs them
    # for real; that is a deliberate two, and a third would be a test nobody is running. The
    # count is printed on every run for the same reason the map counts are.
    outcomes = {name: _count(proc.stdout, rf"(\d+) {name}")
                for name in ("passed", "skipped", "xfailed", "xpassed", "deselected")}
    accounted = sum(outcomes.values())
    if not outcomes["passed"]:
        print("pytest reported no passing tests -- nothing was proven", file=sys.stderr)
        return False
    if accounted < wanted:
        print(f"{wanted} test(s) were collected and {accounted} were accounted for -- "
              f"{wanted - accounted} of them neither ran nor were skipped", file=sys.stderr)
        return False
    said = ", ".join(f"{n} {name}" for name, n in outcomes.items() if n)
    print(f"{wanted} collected test(s), all accounted for: {said}")
    return True


def _count(output: str, pattern: str) -> int:
    """The number pytest printed, or 0 if it printed none."""
    match = re.search(pattern, output)
    return int(match.group(1)) if match else 0


# Every markdown link to a file in this repository resolves. The predecessor repo shipped
# sixty-one references to files that did not exist, several inside runtime error messages.
#
# tools/factory/recipe/ is skipped here and nowhere else: those files are not this repository's
# documents but the bytes an engine receives, and their links resolve against the engine's layout
# (AGENTS.md at its root, not in a recipe directory). Checking them here would compare a rail
# against the wrong tree. tools/tests/factory/test_factory_rails.py checks them against the right
# one -- skipping them without checking them somewhere is the failure this step exists to catch.
#
# .claude/worktrees is where a worktree lands when one is made inside the repository. The rails
# warn that such a worktree is "scanned by a tool that did not expect it", and this is that tool:
# the rails copies under it resolve against an engine's layout, not this repository's, so they
# would all read as broken. git already ignores the directory; so does this.
LINK = re.compile(r"\[[^\]]*\]\(([^)#\s]+)(?:#[^)\s]*)?\)")
LINK_IGNORED_PARTS = {".git", "node_modules"}


def step_doc_references(run: Run) -> bool:
    root = run.root
    ignored_paths = {root / ".claude" / "worktrees"}
    recipe = root / "tools" / "factory" / "recipe"
    broken = examined = 0
    for md in sorted(root.rglob("*.md")):
        if any(part in LINK_IGNORED_PARTS for part in md.parts) or recipe in md.parents:
            continue
        if any(ignored in md.parents for ignored in ignored_paths):
            continue
        for target in LINK.findall(md.read_text(encoding="utf-8", errors="replace")):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            examined += 1
            if not (md.parent / target).resolve().exists():
                broken += 1
                print(f"  X  {md.relative_to(root)} -> {target}")
    if examined == 0:
        print("no repository-relative links found -- this check proved nothing", file=sys.stderr)
        return False
    if broken:
        print(f"\n{broken} of {examined} repository links do not resolve")
        return False
    print(f"{examined} repository link(s) resolve")
    return True


def step_decision_index(run: Run) -> bool:
    """Every decision record is in the index, and every indexed record exists. Numbering is
    permanent here; a record that exists unindexed is one nobody finds."""
    decisions = run.root / "docs" / "decisions"
    index = decisions / "README.md"
    if not index.exists():
        print("docs/decisions/README.md is missing -- nothing to check", file=sys.stderr)
        return False
    listed = set(re.findall(r"\((\d{4}-[^)]+\.md)\)", index.read_text(encoding="utf-8")))
    on_disk = {p.name for p in decisions.glob("[0-9][0-9][0-9][0-9]-*.md")}
    if not on_disk:
        print("no decision records found -- this check proved nothing", file=sys.stderr)
        return False
    bad = False
    for missing in sorted(on_disk - listed):
        print(f"  X  {missing} exists but is not in the index")
        bad = True
    for phantom in sorted(listed - on_disk):
        print(f"  X  {phantom} is indexed but does not exist")
        bad = True
    if bad:
        return False
    print(f"{len(on_disk)} decision record(s), all indexed")
    return True


def step_workflow_pins(run: Run) -> bool:
    """CI runs on an exact Python patch and installs only hash-locked packages (#173). The runner
    and the actions were already pinned; a floating Python or pytest could change this gate's
    verdict with no commit here."""
    return run.python("tools/check-workflow-pins.py")


def step_readme_status(run: Run) -> bool:
    """The README's status table names every subcommand and argument the factory CLI takes, and
    marks what it does not take `not implemented` (#75). The checker imports the parser rather
    than grepping for flags, and fails on a table with no rows."""
    return run.python("tools/check-readme-status.py")


def step_status_issues(run: Run) -> bool:
    """A README sentence that something is "not yet" or "not done" cites an open issue (#170). The
    prose beside #75's table drifted within days of it; this reads GitHub, fails when a state
    cannot be read, and says NOT CHECKED only when RULES_FACTORY_OFFLINE=1 asks it to.

    It is the one step in the gate that needs the network, and what it asks about is a fact about
    two things a diff of code touches neither of: a README sentence, and whether an issue closed.
    So it runs under `--full` -- which is `scripts/validate.sh`, a push to main, and the scheduled
    run -- and not under `--changed`. A diff that touches README.md is placed by no rule and
    widens to `--full` anyway, so the case it exists for still reaches it (#347).

    check-readme-status.py is the other half and stays at every scope: it imports the factory's
    parser rather than reading the network, and a code change is exactly what moves it."""
    if not run.scope.is_full:
        return run.skip("reading GitHub for the state of the issues the README cites")
    return run.python("tools/check-status-issues.py")


# --------------------------------------------------------------------------------------------
# The run
# --------------------------------------------------------------------------------------------

# The order is the order scripts/validate.sh ran them in, and the reasons are the same: the
# boundary check first, because it is a fact about the sources every step below reads; the built
# checker second, because every step after it runs the built file; the tests and the
# repository-wide documents last but one; and what the run left behind last of all, so that it
# sees every step above.
STEPS = (
    ("each subsystem imports only the map contract", step_boundaries),
    ("check-map.py is what the two packages build", step_built_checker),
    ("every map has a row that names its corpora and its grammar", step_fixture_table),
    ("every evidence artifact is the bytes the lock names", step_evidence),
    ("every corpus map satisfies the schema", step_schema),
    ("every map says how its corpus is read", step_protocols),
    ("every protocol's own detectors find its pointers", step_pointers),
    ("every extent's units are enumerated and accounted", step_inventory),
    ("every protocol's required sweeps run and report", step_sweeps),
    ("every corpus map carries a review of its bytes", step_map_reviews),
    ("every blind mapping was given what it recorded", step_blind_staging),
    ("every citation resolves in its corpus", step_locators),
    ("the measured miss rate still describes the validator", step_validator_attack),
    ("every map package passes its publish gate", step_map_packages),
    ("the checkers' own tests", step_tool_tests),
    ("every repository link resolves", step_doc_references),
    ("every decision record is indexed", step_decision_index),
    ("every workflow pins its Python and its packages", step_workflow_pins),
    ("the README's status table matches the factory CLI", step_readme_status),
    ("the README cites no closed issue as not yet done", step_status_issues),
)


def leftovers(root: pathlib.Path) -> list[str]:
    """What git does not track, ignoring the two directories a checkout legitimately carries."""
    found: set[str] = set()
    for args in (["--others", "--exclude-standard", "--ignored", "--directory"],
                 ["--others", "--exclude-standard"]):
        out = subprocess.run(["git", "ls-files", *args], cwd=root,
                             capture_output=True, text=True, check=True).stdout
        found.update(line for line in out.splitlines() if line)
    skipped = (".claude/worktrees/", ".venv/")
    return sorted(p for p in found if not p.startswith(skipped))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="validate-repo.py", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--full", action="store_true",
                        help="every check over every map -- the default")
    parser.add_argument("--changed", action="store_true",
                        help="the checks a diff against --base could have broken")
    parser.add_argument("--release", metavar="MAP",
                        help="every check, packaging only examples/MAP")
    parser.add_argument("--base", metavar="SHA", help="the commit --changed is measured against")
    parser.add_argument("--explain", action="store_true",
                        help="print the scope and the reason for it, and run nothing")
    parser.add_argument("--with-evidence", action="store_true",
                        help="verify every evidence artifact wherever it lives, fetching what "
                             "this checkout does not hold")
    args = parser.parse_args(argv)

    if sum(bool(x) for x in (args.full, args.changed, args.release)) > 1:
        parser.error("--full, --changed and --release are three answers to one question")
    if args.changed and not args.base:
        # Not an error that widens silently: asking for --changed without saying what changed is
        # a mistake in the caller, and running full here would hide it.
        parser.error("--changed needs --base <sha>")

    if args.release:
        scope = release_scope(args.release)
    elif args.changed:
        scope = classify_diff(args.base)
    else:
        scope = full_scope()

    print(f"scope: {scope.name}")
    for reason in scope.reasons:
        print(f"  because {reason}")
    print(f"  maps: {len(scope.maps)} of {len(discover_maps())}"
          f"   packages: {len(scope.packages)} of {len(discover(ROOT, PACKAGE_GLOB))}"
          f"   engine: {'yes' if scope.engine else 'no'}")
    if args.explain:
        for map_path in scope.maps:
            print(f"  map {map_path}")
        for settings in scope.packages:
            print(f"  package {settings}")
        return 0

    # The gate leaves the checkout as it found it (AGENTS.md section 4), and the last step
    # compares what git does not track before and after.
    #
    # That step used to be unable to see the thing it was written to catch. This exported
    # PYTHONDONTWRITEBYTECODE for every child, so a checker that writes bytecode wrote none *here*
    # and left it in any other caller's checkout -- which is exactly what #384 found: the SRD
    # locator checker imports tools/check-locators.py by path, and only the gate's own environment
    # kept tools/__pycache__ out of the tree. A step held to a promise by its caller's environment
    # is holding to it by accident.
    #
    # So the flag is set where it is a property of the tool rather than of the run: each tool that
    # imports another says `sys.dont_write_bytecode = True` for itself, two tests enumerate which
    # tools those are, and the only step that still needs the environment is pytest -- whose xdist
    # workers are separate processes that inherit env and nothing else. Bytecode from anything
    # else now reaches the checkout, where the last step fails on it.
    before = leftovers(ROOT)

    run = Run(ROOT, scope, with_evidence=args.with_evidence)
    for what, fn in STEPS:
        run.run(what, lambda fn=fn: fn(run))

    def nothing_left_behind() -> bool:
        added = [p for p in leftovers(ROOT) if p not in before]
        if added:
            print("this run left files in the checkout:\n" + "\n".join(added), file=sys.stderr)
            return False
        print("nothing untracked or ignored was added by this run")
        return True

    run.run("validate-repo.py left nothing behind in the checkout", nothing_left_behind)

    print()
    if run.failed:
        print("validate-repo.py: FAIL")
        return 1
    print("validate-repo.py: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
