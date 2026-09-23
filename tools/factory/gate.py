"""M3 of #3: the gate recipe. Every engine `produce` writes carries the gate that judges it.

The recipe is the factory's, not the engine's, so it is rewritten on every `produce` (like the
`*.g.cs` files) rather than scaffolded once. Its files are templates under `recipe/`:

  * `scripts/validate.sh` -- the one definition of "acceptable", generalised from
    hoyle-backgammon's hand-built gate: SDK pin; locked restore; merge(package map, overlay)
    under 0015 and the packaged `check-map.py --phase consumer` on the merge; RulesKernel.Randomness
    reachable only as the packaged manifest's `randomness` declares (0019); corpus hash under its declared posture (NOT
    VERIFIED is its own outcome, never ok); every `*.g.cs` equal to a fresh regeneration;
    provenance.json still hashing the generated files, the managed files and the overlay they
    were generated from, so an overlay edit never followed by a re-produce fails (#192);
    format; build and test in Debug and Release, with TRX evidence that the tests ran and that
    every test an implemented entry names exists and ran;
  * `scripts/map-overlay.py` -- merge(package, overlay), 0015 rules 1-5;
  * `scripts/engine-gate.py` -- the gate's non-dotnet checks, one subcommand each;
  * `scripts/factory/*.py` -- this factory's generator and the modules it needs to render every
    `*.g.cs`, verbatim, so the gate can regenerate without the factory. The set is `FILES` below
    and `generate.py` is the name the engine's own scripts import; the rest are what importing it
    reaches: the generator's own parts (`semantics`, `csharp`, `entries`, `registry`, `contracts`,
    `correspondence`, `pins`, `scaffold`, `agentrails` -- #171 split them out of one 88 KB module,
    and an engine cannot import half a generator), ownership.py and rulings.py, rulings.py also by
    map-overlay.py to check the owner's rulings of decision 0027; provenance.py's embedding, which
    imports intake; and intake.py's HASH_DERIVATIONS, the one table engine-gate.py's posture
    recomputes a baseline with; and overlay.py, which is where the engine's own evidence is read
    from and is read by all of them. Every file written here is in provenance.json's `generated`,
    which is what ties these bytes to a factory version;
  * `.github/workflows/validate.yml` -- runs `validate.sh full` and nothing else.

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
    "scripts/factory/agentrails.py": (os.path.join(HERE, "agentrails.py"), False),
    # The engine's own gate reproduces the map the factory merged, and for a composed engine that
    # means composing the restored packages before the overlay is applied (0067).
    "scripts/factory/compose.py": (os.path.join(HERE, "compose.py"), False),
    "scripts/factory/contracts.py": (os.path.join(HERE, "contracts.py"), False),
    "scripts/factory/correspondence.py": (os.path.join(HERE, "correspondence.py"), False),
    "scripts/factory/csharp.py": (os.path.join(HERE, "csharp.py"), False),
    "scripts/factory/entries.py": (os.path.join(HERE, "entries.py"), False),
    "scripts/factory/generate.py": (os.path.join(HERE, "generate.py"), False),
    "scripts/factory/intake.py": (os.path.join(HERE, "intake.py"), False),
    "scripts/factory/pins.py": (os.path.join(HERE, "pins.py"), False),
    "scripts/factory/registry.py": (os.path.join(HERE, "registry.py"), False),
    "scripts/factory/scaffold.py": (os.path.join(HERE, "scaffold.py"), False),
    "scripts/factory/semantics.py": (os.path.join(HERE, "semantics.py"), False),
    "scripts/factory/overlay.py": (os.path.join(HERE, "overlay.py"), False),
    "scripts/factory/ownership.py": (os.path.join(HERE, "ownership.py"), False),
    "scripts/factory/provenance.py": (os.path.join(HERE, "provenance.py"), False),
    "scripts/factory/rulings.py": (os.path.join(HERE, "rulings.py"), False),
    ".github/workflows/validate.yml": (os.path.join(RECIPE, "validate.yml"), False),
}


def files(name):
    """The recipe for engine `name`: published path -> (bytes, executable)."""
    out = {}
    for relative, (source, executable) in FILES.items():
        with open(source, "rb") as handle:
            data = handle.read()
        if relative == "scripts/validate.sh":
            data = data.replace(b"@NAME@", name.encode("ascii"))
        out[relative] = (data, executable)
    return out


def emit(name, out, log=None):
    for relative, (data, executable) in files(name).items():
        path = os.path.join(out, *relative.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(data)
        os.chmod(path, 0o755 if executable else 0o644)
        if log is not None:
            print(f"wrote {relative}", file=log)
