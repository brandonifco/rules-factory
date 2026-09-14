"""M4 of #3: provenance. What an engine was produced from, recorded so it can be recomputed.

`produce` writes `provenance.json` in the engine root, last, after every other step. The
engine embeds it (`<Name>.provenance.json`, from the src project) and a generated test asserts
the embedded copy is byte-identical to the file, so a built assembly carries the record of
what it was built from.

The fields, and where each comes from:

  * `engine.name` -- the `--name` given to `produce` (recompute needs it to re-produce).
  * `factory` -- the rules-factory checkout this module is in:
      - `version`: `X.Y.Z` when HEAD carries a tag `factory/vX.Y.Z` (the highest, if several);
        otherwise `0.0.0-dev+<the first 12 hex digits of HEAD>`. Twelve is fixed rather than
        git's `--short`, whose length grows with the repository.
      - `commit`: the full SHA of HEAD.
      - `dirty`: whether `git status --porcelain` lists anything. `produce` refuses a dirty
        tree unless `--allow-dirty`, and then records `true`. A factory that is not a git
        checkout is refused outright: its commit cannot be named.
  * `map` -- the package id and version from its nuspec, the SHA-256 of the `.nupkg` bytes,
    and the SHA-256 of the map, manifest and consumer checker at the paths the package's
    props name (`map/corpus-map.json`, `map/corpus-manifest.json`, `tools/check-map.py`).
  * `corpus` -- sourceId, contentHash, hashDerivation and asOf of the one corpus, with
    `recomputed: true`: intake derived contentHash from the corpus bytes under
    hashDerivation and it matched; it was not copied from the map.
  * `kernel` -- the RulesKernel version the engine references.
  * `packs` -- `[]`: no rule packs exist yet, and the empty list says so rather than omitting it.
  * `recipes` -- every file under `tools/factory/` (the factory's templates are its Python
    modules), `__pycache__` and `*.pyc` excluded, and `tools/check-map.py` beside it (the
    checker intake runs decides whether there is any output, so it is factory code too, and a
    factory without it is refused), each with its SHA-256, sorted by
    repository-relative POSIX path in ascending byte order; and `digest`, the SHA-256 of the
    UTF-8 text made of one line `<sha256>  <path>\\n` per file in that order (`sha256sum` format).
  * `generated` -- `[{path, sha256}]`, sorted by path, for every file `produce` wrote on this
    run under the engine directory, except `provenance.json` itself and the write-once scaffold
    (generate.scaffold): scaffold files belong to the engine after the first run and a second
    run leaves them alone, so hashing them would make an engine's own edits (its overlay above
    all) look like tampering, and would make a fresh run and a re-run disagree. Leaving them out
    is only safe because no scaffold file says anything the inputs decide: the kernel and map
    pins and the map's PackageReference live in the generated `RulesFactory.Packages.g.props`,
    which is listed here like any `*.g.cs` (#66). The list is not
    hard-coded: `Recorder` notes every path opened for writing (or renamed into place) while
    `produce` runs, so a later step's output is picked up without touching this module.
    Writes made by a child process are not seen; no step makes any.
  * `randomness` -- `"none"`: nothing the factory emits depends on a random source.

Deterministic: no timestamps, no machine paths; two runs from the same inputs are identical.

`recompute(engine_dir, produce_into, package)` re-produces the engine in a scratch copy from
the same package and the engine's committed corpus, and returns every mismatch as a line naming
the field (`map.nupkgSha256`, `corpus.contentHash`, `recipes.files[tools/factory/generate.py]`,
`generated[src/X/Generated/MapEntries.g.cs]`, ...). It also hashes each recorded generated file
on disk, so a hand edit to a generated file (a pin in RulesFactory.Packages.g.props included) is
caught even though re-producing would undo it.
An empty list means the record is true of the engine and the factory running the check.

Standard library only.
"""
import builtins
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tempfile

import generate
import intake as intake_step

FILE_NAME = "provenance.json"
FORMAT = 1
FACTORY_DIR = os.path.dirname(os.path.abspath(__file__))
TAG = re.compile(r"^factory/v(\d+)\.(\d+)\.(\d+)$")
SHORT_SHA = 12
DIGEST_RULE = ("sha256 over UTF-8 lines '<sha256>  <path>\\n', one per recipe file, "
               "in ascending byte order of path")
COPY_IGNORE = shutil.ignore_patterns("bin", "obj", ".git", ".vs")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    with open(path, "rb") as handle:
        return sha256(handle.read())


# --- the factory -----------------------------------------------------------------------------


def _git(factory_dir, *args):
    try:
        done = subprocess.run(["git", "-C", factory_dir, *args], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise intake_step.Refused(f"cannot run git to identify the factory: {error}")
    if done.returncode != 0:
        raise intake_step.Refused(f"the factory at {factory_dir} is not a git checkout whose commit can be "
                                  f"named (git {' '.join(args)}: {done.stderr.strip()})")
    return done.stdout


def factory_state(factory_dir=FACTORY_DIR):
    commit = _git(factory_dir, "rev-parse", "HEAD").strip()
    tags = []
    for line in _git(factory_dir, "tag", "--points-at", "HEAD").splitlines():
        match = TAG.match(line.strip())
        if match:
            tags.append(tuple(int(part) for part in match.groups()))
    version = ".".join(map(str, max(tags))) if tags else f"0.0.0-dev+{commit[:SHORT_SHA]}"
    dirty = bool(_git(factory_dir, "status", "--porcelain").strip())
    top = os.path.realpath(_git(factory_dir, "rev-parse", "--show-toplevel").strip())
    return {"version": version, "commit": commit, "dirty": dirty, "_top": top}


def require_clean(state, allow_dirty):
    if state["dirty"] and not allow_dirty:
        raise intake_step.Refused(f"the factory working tree ({state['_top']}) has uncommitted changes, so "
                                  f"provenance could not name what produced the engine; commit them, or "
                                  f"pass --allow-dirty to produce anyway and record dirty: true")


# Factory code outside tools/factory that decides the output, relative to tools/factory's parent.
RECIPES_BESIDE = ("check-map.py",)


def recipes(factory_dir, top):
    files = []
    for name in RECIPES_BESIDE:
        path = os.path.join(os.path.dirname(os.path.abspath(factory_dir)), name)
        if not os.path.isfile(path):
            raise intake_step.Refused(f"the factory has no {path}, so provenance could not name the checker "
                                      f"intake runs")
        files.append({"path": os.path.relpath(os.path.realpath(path), top).replace(os.sep, "/"),
                      "sha256": sha256_file(path)})
    for directory, dirs, names in os.walk(factory_dir):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in names:
            if name.endswith(".pyc"):
                continue
            path = os.path.join(directory, name)
            files.append({"path": os.path.relpath(os.path.realpath(path), top).replace(os.sep, "/"),
                          "sha256": sha256_file(path)})
    files.sort(key=lambda f: f["path"].encode("utf-8"))
    text = "".join(f"{f['sha256']}  {f['path']}\n" for f in files)
    return {"files": files, "digestRule": DIGEST_RULE, "digest": sha256(text.encode("utf-8"))}


# --- what produce writes ---------------------------------------------------------------------


class Recorder:
    """Notes every file opened for writing, or renamed into place, under `out` while active."""

    WRITE_MODES = set("wax+")

    def __init__(self, out):
        self.root = os.path.realpath(os.path.abspath(out))
        self.paths = set()

    def _note(self, target):
        if isinstance(target, (str, bytes, os.PathLike)):
            path = os.path.realpath(os.path.abspath(os.fsdecode(target)))
            if path.startswith(self.root + os.sep):
                self.paths.add(os.path.relpath(path, self.root).replace(os.sep, "/"))

    def __enter__(self):
        self._saved = (builtins.open, io.open, os.replace, os.rename)
        real_open, _, real_replace, real_rename = self._saved

        def recording_open(file, mode="r", *args, **kwargs):
            if self.WRITE_MODES & set(mode):
                self._note(file)
            return real_open(file, mode, *args, **kwargs)

        def recording_replace(src, dst, *args, **kwargs):
            self._note(dst)
            return real_replace(src, dst, *args, **kwargs)

        def recording_rename(src, dst, *args, **kwargs):
            self._note(dst)
            return real_rename(src, dst, *args, **kwargs)

        builtins.open = io.open = recording_open
        os.replace, os.rename = recording_replace, recording_rename
        return self

    def __exit__(self, *exc):
        builtins.open, io.open, os.replace, os.rename = self._saved
        return False


# --- the embedded copy -----------------------------------------------------------------------


PROVENANCE_CS = """namespace @NAME@;

/// <summary>The engine's provenance.json (rules-factory #3, M4), embedded when the assembly was built.</summary>
public static class EngineProvenance
{
    /// <summary>The manifest resource name provenance.json is embedded under.</summary>
    public const string ResourceName = "@NAME@.provenance.json";

    /// <summary>The embedded provenance.json, byte for byte.</summary>
    /// <returns>The file's bytes.</returns>
    /// <exception cref="InvalidOperationException">The assembly was built without it.</exception>
    public static byte[] ReadBytes()
    {
        using var stream = typeof(EngineProvenance).Assembly.GetManifestResourceStream(ResourceName)
            ?? throw new InvalidOperationException($"the assembly has no embedded {ResourceName}");
        using var copy = new MemoryStream();
        stream.CopyTo(copy);
        return copy.ToArray();
    }
}
"""

PROVENANCE_TESTS_CS = """using Xunit;

namespace @NAME@.Tests;

public sealed class ProvenanceTests
{
    [Fact]
    public void The_embedded_provenance_is_byte_identical_to_provenance_json_in_the_engine_root() =>
        Assert.Equal(File.ReadAllBytes(EngineRootFile("provenance.json")), EngineProvenance.ReadBytes());

    private static string EngineRootFile(string name)
    {
        for (var directory = new DirectoryInfo(AppContext.BaseDirectory); directory is not null; directory = directory.Parent)
        {
            var candidate = Path.Combine(directory.FullName, name);
            if (File.Exists(candidate) && File.Exists(Path.Combine(directory.FullName, "@NAME@.slnx")))
            {
                return candidate;
            }
        }

        throw new FileNotFoundException($"no {name} beside @NAME@.slnx above {AppContext.BaseDirectory}");
    }
}
"""


def embedding(model):
    """The generated C# that reads and tests the embedded copy (the src project embeds the file)."""
    name = model.name
    return {
        f"src/{name}/Generated/Provenance.g.cs": model.header + PROVENANCE_CS.replace("@NAME@", name),
        f"tests/{name}.Tests/Generated/ProvenanceTests.g.cs": model.header + PROVENANCE_TESTS_CS.replace("@NAME@", name),
    }


def emit(model, out):
    for relative, text in embedding(model).items():
        path = os.path.join(out, *relative.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(text.encode("utf-8"))


# --- the record ------------------------------------------------------------------------------


def build(state, result, model, recorder, factory_dir=FACTORY_DIR):
    corpus = result.corpus
    write_once = set(generate.scaffold(model).keys())
    generated_files = []
    for relative in sorted(recorder.paths, key=lambda p: p.encode("utf-8")):
        if relative == FILE_NAME or relative in write_once:
            continue
        generated_files.append({"path": relative, "sha256": sha256_file(os.path.join(recorder.root, *relative.split("/")))})
    return {
        "provenanceFormat": FORMAT,
        "engine": {"name": model.name},
        "factory": {"version": state["version"], "commit": state["commit"], "dirty": state["dirty"]},
        "map": {
            "packageId": result.package_id,
            "version": result.version,
            "nupkgSha256": result.nupkg_sha256,
            "files": [{"role": role, "path": result.part_paths[role], "sha256": sha256(raw)}
                      for role, raw in (("map", result.map_raw), ("manifest", result.manifest_raw),
                                        ("checker", result.checker_raw))],
        },
        "corpus": {
            "sourceId": corpus["sourceId"],
            "contentHash": corpus["contentHash"],
            "hashDerivation": corpus["hashDerivation"],
            "asOf": corpus.get("asOf"),
            "recomputed": True,
        },
        "kernel": {"packageId": "RulesKernel", "version": generate.KERNEL_VERSION},
        "packs": [],
        "recipes": recipes(factory_dir, state["_top"]),
        "generated": generated_files,
        "randomness": "none",
    }


def serialize(document):
    return (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def write(out, document):
    with open(os.path.join(out, FILE_NAME), "wb") as handle:
        handle.write(serialize(document))


# --- recompute -------------------------------------------------------------------------------


def _keyed(items):
    """A list of objects keyed by path (or role) compares by that key, not by position."""
    if items and all(isinstance(i, dict) and ("path" in i or "role" in i) for i in items):
        return {str(i.get("path", i.get("role"))): {k: v for k, v in i.items() if k not in ("path",)} for i in items}
    return None


def diff(recorded, actual, field=""):
    if isinstance(recorded, dict) and isinstance(actual, dict):
        out = []
        for key in list(recorded) + [k for k in actual if k not in recorded]:
            name = f"{field}.{key}" if field else key
            if key not in actual:
                out.append(f"{name}: recorded {json.dumps(recorded[key])}, recomputed nothing")
            elif key not in recorded:
                out.append(f"{name}: recorded nothing, recomputed {json.dumps(actual[key])}")
            else:
                out.extend(diff(recorded[key], actual[key], name))
        return out
    if isinstance(recorded, list) and isinstance(actual, list):
        left, right = _keyed(recorded), _keyed(actual)
        if left is not None and right is not None:
            out = []
            for key in sorted(set(left) | set(right)):
                name = f"{field}[{key}]"
                if key not in right:
                    out.append(f"{name}: recorded, recomputed nothing")
                elif key not in left:
                    out.append(f"{name}: not recorded, recomputed {json.dumps(right[key])}")
                else:
                    out.extend(diff(left[key], right[key], name))
            if [str(i.get("path", i.get("role"))) for i in recorded] != [str(i.get("path", i.get("role"))) for i in actual] \
                    and set(left) == set(right):
                out.append(f"{field}: recorded in a different order")
            return out
    if recorded != actual:
        return [f"{field}: recorded {json.dumps(recorded)}, recomputed {json.dumps(actual)}"]
    return []


def recompute(engine_dir, produce_into, package=None):
    """Every way `engine_dir/provenance.json` is not what re-producing gives; [] when it is.

    `produce_into(package, corpus, name, out)` runs the whole of `produce` with --allow-dirty and
    returns the provenance document it wrote (raising intake.Refused or GenerationError).
    """
    path = os.path.join(engine_dir, FILE_NAME)
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
        recorded = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as error:
        return [f"{FILE_NAME}: cannot be read ({error})"]
    if not isinstance(recorded, dict):
        return [f"{FILE_NAME}: not a JSON object"]
    mismatches = []
    if raw != serialize(recorded):
        mismatches.append(f"{FILE_NAME}: not in the factory's canonical form (edited by hand?)")

    # Generated files on disk: re-producing rewrites them, so a hand edit is only visible here.
    for item in recorded.get("generated") or []:
        where = os.path.join(engine_dir, *str(item.get("path")).split("/"))
        if not os.path.isfile(where):
            mismatches.append(f"generated[{item.get('path')}]: recorded, missing on disk")
        elif sha256_file(where) != item.get("sha256"):
            mismatches.append(f"generated[{item.get('path')}].sha256: recorded {item.get('sha256')}, "
                              f"on disk {sha256_file(where)}")

    corpus = recorded.get("corpus") or {}
    corpus_files = [g["path"] for g in recorded.get("generated") or [] if str(g.get("path", "")).startswith("corpus/")]
    if len(corpus_files) != 1:
        return mismatches + [f"generated: names {len(corpus_files)} corpus/ files; exactly one is the corpus"]
    corpus_path = os.path.join(engine_dir, *corpus_files[0].split("/"))
    derive = intake_step.HASH_DERIVATIONS.get(corpus.get("hashDerivation"))
    if derive is None:
        mismatches.append(f"corpus.hashDerivation: {corpus.get('hashDerivation')!r} cannot be computed")
    elif os.path.isfile(corpus_path):
        with open(corpus_path, "rb") as handle:
            actual = derive(handle.read())
        if actual != corpus.get("contentHash"):
            mismatches.append(f"corpus.contentHash: recorded {corpus.get('contentHash')}, {corpus_files[0]} "
                              f"gives {actual} under {corpus.get('hashDerivation')}")

    source = recorded.get("map") or {}
    name = (recorded.get("engine") or {}).get("name")
    spec = package or f"{source.get('packageId')}@{source.get('version')}"
    with tempfile.TemporaryDirectory(prefix="factory-recompute-") as scratch:
        copy = os.path.join(scratch, "engine")
        shutil.copytree(engine_dir, copy, ignore=COPY_IGNORE)
        try:
            actual = produce_into(spec, os.path.join(copy, *corpus_files[0].split("/")), name, copy)
        except (intake_step.Refused, intake_step.Usage, generate.GenerationError) as error:
            return mismatches + [f"produce refused to re-produce the engine, so nothing else was compared: {error}"]
    for line in diff(recorded, actual):
        if line not in mismatches:
            mismatches.append(line)
    return mismatches
