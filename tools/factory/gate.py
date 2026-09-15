"""M3 of #3: the gate recipe. Every engine `produce` writes carries the gate that judges it.

The recipe is the factory's, not the engine's, so it is rewritten on every `produce` (like the
`*.g.cs` files) rather than scaffolded once. Its files are templates under `recipe/`:

  * `scripts/validate.sh` -- the one definition of "acceptable", generalised from
    hoyle-backgammon's hand-built gate: SDK pin; locked restore; merge(package map, overlay)
    under 0015 and the packaged `check-map.py --phase consumer` on the merge; RulesKernel.Randomness
    reachable only as the packaged manifest's `randomness` declares (0019); corpus hash under its declared posture (NOT
    VERIFIED is its own outcome, never ok); every `*.g.cs` equal to a fresh regeneration;
    format; build and test in Debug and Release, with TRX evidence that the tests ran and that
    every test an implemented entry names exists and ran;
  * `scripts/map-overlay.py` -- merge(package, overlay), 0015 rules 1-5;
  * `scripts/engine-gate.py` -- the gate's non-dotnet checks, one subcommand each;
  * `scripts/factory/{generate,intake,ownership,provenance,rulings}.py` -- this factory's generator and
    the modules it needs to render every `*.g.cs` (ownership.py and rulings.py, which generate.py
    imports, rulings.py also by map-overlay.py to check the owner's rulings of decision 0027;
    provenance.py's embedding, which imports intake; and intake.py's HASH_DERIVATIONS, the one
    table engine-gate.py's posture recomputes a baseline with), verbatim,
    so the gate can regenerate without the factory. Every file written here is in
    provenance.json's `generated`, which is what ties these bytes to a factory version;
  * `.github/workflows/validate.yml` -- runs `validate.sh full` and nothing else. For an engine of a
    licensed `local-copy` corpus (decisions 0022 and 0028) it is `recipe/validate-local-copy.yml`
    instead: no runner can restore that engine's map, so CI runs what needs no licensed input (the
    SDK pin, lock files present, nothing licensed committed, whitespace formatting, and the projects
    that do not depend on the map) and reports NOT VERIFIED as a passing job of its own, never as
    a failure and never as verified. `validate.sh full` stays the one definition of acceptable, run
    on the operator's machine. Every other engine's workflow is byte-identical to what it was.

Lock files are not written here: they need a restore, and `produce` runs no dotnet. The emitted
`Directory.Build.props` (generate.py) turns lock files on and CI restores in locked mode;
`./scripts/validate.sh lock` writes them once, to be committed.

Standard library only.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
RECIPE = os.path.join(HERE, "recipe")

# published path -> (template under recipe/ or this directory, executable)
FILES = {
    "scripts/validate.sh": (os.path.join(RECIPE, "validate.sh"), True),
    "scripts/map-overlay.py": (os.path.join(RECIPE, "map-overlay.py"), True),
    "scripts/engine-gate.py": (os.path.join(RECIPE, "engine-gate.py"), True),
    "scripts/factory/generate.py": (os.path.join(HERE, "generate.py"), False),
    "scripts/factory/intake.py": (os.path.join(HERE, "intake.py"), False),
    "scripts/factory/ownership.py": (os.path.join(HERE, "ownership.py"), False),
    "scripts/factory/provenance.py": (os.path.join(HERE, "provenance.py"), False),
    "scripts/factory/rulings.py": (os.path.join(HERE, "rulings.py"), False),
    ".github/workflows/validate.yml": (os.path.join(RECIPE, "validate.yml"), False),
}

# Decision 0028: the workflow of an engine whose corpus is licensed local-copy.
LOCAL_COPY_WORKFLOW = os.path.join(RECIPE, "validate-local-copy.yml")


def files(name, local_copy=False):
    """The recipe for engine `name`: published path -> (bytes, executable). `local_copy` is whether the
    engine's corpus is a licensed local-copy one (0028), which changes the CI workflow and nothing else."""
    out = {}
    for relative, (source, executable) in FILES.items():
        if local_copy and relative == ".github/workflows/validate.yml":
            source = LOCAL_COPY_WORKFLOW
        with open(source, "rb") as handle:
            data = handle.read()
        if relative == "scripts/validate.sh":
            data = data.replace(b"@NAME@", name.encode("ascii"))
        out[relative] = (data, executable)
    return out


def emit(name, out, log=None, local_copy=False):
    for relative, (data, executable) in files(name, local_copy).items():
        path = os.path.join(out, *relative.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(data)
        os.chmod(path, 0o755 if executable else 0o644)
        if log is not None:
            print(f"wrote {relative}", file=log)
