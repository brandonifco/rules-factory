"""M2 of #3: scaffold a .NET engine and generate the `*.g.cs` files that tie it to its map.

Three kinds of output, one per ownership class (ownership.py holds the table, decision 0018):

  * **Managed** -- global.json, NuGet.config and Directory.Build.props (`managed_files`): the
    factory's build policy. Rewritten when the recipe version moves and the engine has not
    edited them; a hand edit is refused unless `--adopt` or `--reset` settles it.
  * **Engine-owned** -- Directory.Packages.props, the solution and both project files
    (`engine_owned`). Written only when absent: after the first `produce` they belong to the
    engine, and a second `produce` must not undo an edit to them. The engine's overlay
    (`overlay/<entry id>.json`, 0015 and #247) is engine-owned too and is scaffolded by nothing: a
    file appears when an entry is implemented, and an engine with no implemented entry has an
    empty overlay because it has nothing to say. `produce` only ever writes one of them to migrate
    an engine produced before #247 (`overlay.split`).
    Neither managed nor engine-owned files may say anything the factory's inputs decide. A
    re-run with a different map version would leave such a file naming the old one while the
    code and provenance.json named the new (#66).
  * **Generated** -- every file named `*.g.*`: the `*.g.cs` under `Generated/`, and
    `RulesFactory.Packages.g.props` in the engine root. Rewritten on every `produce`, from the
    package map merged with the engine's overlay, and never edited by hand; provenance.json
    hashes each one. Hand-written code lives in any other file and is never touched.


The corpus is copied to `corpus/` on every run; intake has already proved its bytes, and that its
licence permits committing them (decision 0028).

What is where. This module is the composition: it decides what `produce` writes, in what order,
and under which ownership class. It is also the name an engine knows the generator by -- the gate
vendors these modules under `scripts/factory/`, and the engine's `scripts/engine-gate.py`
regenerates through `generate.generated`, so the names re-exported below are an interface a
produced engine depends on and not a convenience.

  * `semantics.py` -- the overlay merge (0015), the correspondence table, the C# member names and
    the typed contract of one entry: the map as the renderers receive it;
  * `csharp.py` -- the escapes, the header and the literals every renderer shares;
  * `entries.py` -- `MapEntries.g.cs` and `Rulings.g.cs`;
  * `registry.py` -- `Registry.g.cs`;
  * `contracts.py` -- `Contracts.g.cs` and `Requests.g.cs`;
  * `correspondence.py` -- `CorrespondenceTests.g.cs`;
  * `pins.py` -- every version the factory pins, and `RulesFactory.Packages.g.props`;
  * `scaffold.py` -- the managed and engine-owned files;
  * `agentrails.py` -- the agent rails (0029) and the one reading of `.github/agent-policy.json`.

Deterministic: the output depends only on the package map (its id and version included), the
overlay, the corpus, the engine name and the factory's own pins. No timestamps, no machine
paths, no dictionary-order accidents.
"""
import json
import os

import agentrails
import contracts
import correspondence
import entries
import overlay as overlay_step
import ownership
import pins
import registry
import rulings as rulings_step
import scaffold
import semantics

# The generator's name for the things a produced engine reaches through `import generate`. The gate
# vendors this module and the ones it imports as `scripts/factory/*.py`, where `scripts/engine-gate.py`
# regenerates the `*.g.cs` files and judges `.github/agent-policy.json` through it, `tools/entry-packet.py`
# renders an entry's packet through it, and `tools/agent-doctor.py` reads the rails' state through it.
# Those files run inside engines this factory produced months ago, so the set is an interface: a name
# taken off it breaks every engine's gate at once, and tools/tests/factory/test_factory_modules.py
# holds it to what the recipe actually reaches for.
GenerationError = semantics.GenerationError
Model = semantics.Model
merge = semantics.merge
first_row = semantics.first_row
contract = semantics.contract
policy_problems = agentrails.policy_problems
review_problems = agentrails.review_problems
RAILS = agentrails.RAILS
# tools/validate-engine.py reads the SDK pin by importing this module, as the engines do.
SDK_VERSION = pins.SDK_VERSION


def generated(model):
    name = model.name
    files = {
        pins.PACKAGES_PROPS: pins.packages_props(model),
        f"src/{name}/Generated/MapEntries.g.cs": entries.map_entries_cs(model),
        f"src/{name}/Generated/Registry.g.cs": registry.registry_cs(model),
        f"src/{name}/Generated/Contracts.g.cs": contracts.contracts_cs(model),
        f"src/{name}/Generated/Requests.g.cs": contracts.requests_cs(model),
        f"tests/{name}.Tests/Generated/CorrespondenceTests.g.cs": correspondence.tests_cs(model),
    }
    if model.rulings:
        files[f"src/{name}/Generated/{entries.RULINGS_FILE}"] = entries.rulings_cs(model)
    return files


def _write(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data)


def split_notes(out, split):
    """What a run that migrated the overlay should say, if it migrated one (#247).

    The second line is the one a reader would otherwise find out the hard way.
    `.github/agent-policy.json` is engine-owned (decision 0029): the factory writes it once and
    never again, so an engine produced before #247 still lists `corpus-map.overlay.json` among the
    paths that ask for a semantic review. After the migration that path no longer exists, and a
    change to the evidence would stop asking for the review it used to ask for. The factory will not
    edit an engine's own configuration to fix that, so it says so instead, every run, until the
    engine changes it.
    """
    if not split:
        return []
    lines = [f"--- migrated {overlay_step.RETIRED_NAME} to {len(split)} file(s) under "
             f"{overlay_step.DIRECTORY}/, one per entry, so two entry branches never write the same "
             f"file (#247); the old file is removed below if these carry all of it"]
    try:
        with open(os.path.join(out, *agentrails.AGENT_POLICY.split("/")), encoding="utf-8") as handle:
            policy = json.load(handle)
        paths = ((policy.get("review") or {}).get("semanticPaths") or [])
    except (OSError, ValueError, AttributeError):
        paths = []
    if overlay_step.RETIRED_NAME in paths:
        lines.append(f"--- {agentrails.AGENT_POLICY} still lists {overlay_step.RETIRED_NAME} in review.semanticPaths, and "
                     f"that file is going. It is engine-owned (0029), so this run will not edit it: replace "
                     f"that entry with {overlay_step.DIRECTORY}/** yourself, or a change to this engine's "
                     f"evidence stops asking for the semantic review it used to ask for")
    return lines


def produce(intake, name, out, log=None, adopt=(), reset=()):
    """Write an engine for `intake` under `out`, each file as its ownership class says.

    Engine-owned files are written when absent; managed files as ownership.plan_managed decides
    (`adopt` and `reset` are the managed paths given to --adopt and --reset); generated files
    always. The returned model carries `managed` ({path: recipe version}) and `adopted` (managed
    paths now engine-owned) for provenance to record. Every refusal is raised before any write.
    """
    # #247: the overlay is one file per entry. An engine produced before it has the one shared
    # corpus-map.overlay.json and no overlay/ directory; the split writes its keys out, one file
    # each, and ownership.remove_retired -- later in the run, in the same transaction -- deletes the
    # old file if and only if these files carry every key of it (overlay.superseded_by_split).
    try:
        split = overlay_step.split(out)
        overlay = overlay_step.load(out, intake.map)
    except overlay_step.OverlayError as error:
        raise GenerationError(str(error))
    model = Model(intake, merge(intake.map, overlay, root=out), name, rulings_step.collect(overlay))
    pins.refuse_split_pins(model, out)
    try:
        managed_writes, model.managed, model.adopted, notes = ownership.plan_managed(
            out, name, {p: t.encode("utf-8") for p, t in scaffold.managed_files().items()}, adopt, reset)
    except ownership.OwnershipError as error:
        raise GenerationError(str(error))
    # Every corpus the map cites is shipped with the engine, not only the principal one: a rule
    # the map states from § 172.102 is unreadable beside an engine carrying only § 172.101 (0039).
    corpus_files = {v["sourceId"]: os.path.basename(str(v["corpus"].get("committedPath") or v["name"]))
                    for v in intake.corpora}
    if len(set(corpus_files.values())) != len(corpus_files):
        raise GenerationError(f"two cited corpora are committed under the same file name "
                              f"({', '.join(sorted(corpus_files.values()))}); an engine's corpus/ "
                              f"directory would hold one of them")

    written = []
    for relative, text in scaffold.engine_owned(model).items():
        path = os.path.join(out, *relative.split("/"))
        if not os.path.exists(path):
            _write(path, text.encode("utf-8"))
            written.append(relative)
    for relative, data in sorted(managed_writes.items()):
        path = os.path.join(out, *relative.split("/"))
        _write(path, data)
        if relative in agentrails.EXECUTABLE:
            os.chmod(path, 0o755)
        written.append(relative)
    for verified in intake.corpora:
        name_on_disk = corpus_files[verified["sourceId"]]
        _write(os.path.join(out, "corpus", name_on_disk), verified["bytes"])
        written.append(f"corpus/{name_on_disk}")
    for relative, text in generated(model).items():
        _write(os.path.join(out, *relative.split("/")), text.encode("utf-8"))
        written.append(relative)
    # An engine whose last ruling was withdrawn no longer generates the rulings file (0027); left in
    # place, it would be a stray *.g.cs the gate refuses.
    stale_rulings = os.path.join(out, "src", name, "Generated", entries.RULINGS_FILE)
    if not model.rulings and os.path.isfile(stale_rulings):
        os.remove(stale_rulings)
        written.append(f"(removed) src/{name}/Generated/{entries.RULINGS_FILE}")
    if log is not None:
        rows = {}
        for item in model.entries:
            rows[item["row"]] = rows.get(item["row"], 0) + 1
        summary = ", ".join(f"row {r}: {n}" if r else f"no row: {n}" for r, n in sorted(rows.items(), key=lambda kv: kv[0] or 0))
        print(f"--- produce: {len(model.entries)} entries registered ({summary})", file=log)
        for line in split_notes(out, split):
            print(line, file=log)
        for line in rulings_step.describe(overlay):
            print(f"--- {line}", file=log)
        for note in notes:
            print(note, file=log)
        for relative in written:
            print(f"wrote {relative}", file=log)
    return model
