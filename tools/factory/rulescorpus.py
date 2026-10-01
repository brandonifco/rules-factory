"""The one way a corpus is built and its baseline verified: rules-corpus, at a pinned commit (#558).

The factory once carried its own digest recipe, a `HASH_DERIVATIONS` table in intake.py that every
engine received a copy of, and the copies drifted (rules-corpus#4). A corpus is now described by
a committed rules-corpus **build definition**, and rules-corpus is the only thing that turns that
definition and the committed bytes into a baseline. This module orchestrates it; it computes no
digest of its own.

**Where a corpus's recipe lives.** Beside the corpus file `F`, with F's stem:

  * `<stem>.corpus.build.json`: the rules-corpus build definition. It declares F as a stored
    source (at the path F's own name) and a baseline naming the artifact the map cites, by
    `sourceId`, `hashDerivation` and `asOf`. Every other stored source it declares is resolved
    beside F too.
  * `<stem>.corpus.expect.json`: `{"expectNotVerified": [...]}`, the checks this consumer accepts
    as not verified, by the names `rules-corpus verify` prints (rules-corpus decision 0008). It is
    required, and `[]` says that nothing may be left unverified. A check that is not verified and
    not named fails, and so does a named check that is verified after all.

**Which rules-corpus.** `REPOSITORY` at `COMMIT`, below and nowhere else. The checkout is made
by this module under the user's cache directory, keyed by the commit, and checked against the pin
before every use: its HEAD must be `COMMIT` and its tracked files unmodified. A checkout that
fails either check is refused, never repaired or used. It is run with `dotnet run` against its own
`global.json`. That is how a checkout is pinned before rules-corpus publishes a tool (its
milestone M7); the pin then becomes a package version and nothing here changes its meaning.

**How a corpus is judged.** The definition, the expectation and every stored source are copied
into a fresh temporary directory, then `rules-corpus build` and `rules-corpus verify --rebuild`
run there, with `--expect-not-verified` when the expectation names anything. Anything but exit 0
from either command is a refusal carrying the tool's own report. There is no fallback: when the
tool cannot be fetched, built or run, nothing is verified.

Standard library only; vendored into every engine as scripts/factory/rulescorpus.py, where the
engine's gate imports it through intake.py.
"""
import contextlib
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import tempfile

REPOSITORY = "https://github.com/brandonifco/rules-corpus"
COMMIT = "ffc04287774917e8721c743db0749dffde2afcbe"
CLI_PROJECT = "src/RulesCorpus.Cli/RulesCorpus.Cli.csproj"

DEFINITION_SUFFIX = ".corpus.build.json"
EXPECTATION_SUFFIX = ".corpus.expect.json"

# Verified builds already made in this process, by the identity of everything they were made from:
# the pin, the checkout's location, and the exact bytes of the definition, the expectation and every
# stored source. rules-corpus's own promise -- and its gate's evidence -- is that the same bytes and
# the same declared derivation produce the same corpus, so asking it again within one process learns
# nothing; the factory asks once per corpus per run of produce, and its test suite asked the same
# few corpora some three thousand times (#558). Only a verified result is kept: a refusal is always
# asked again, and nothing is kept on disk or across processes.
_VERIFIED = {}


class Refused(Exception):
    """The corpus is not what its definition and expectation say, or they are malformed."""


class Unavailable(Exception):
    """The pinned rules-corpus could not be fetched, built or run: nothing was verified."""


def companions(corpus_path):
    """(definition path, expectation path) for the corpus file at `corpus_path`."""
    directory, name = os.path.split(corpus_path)
    stem = os.path.splitext(name)[0]
    return (os.path.join(directory, stem + DEFINITION_SUFFIX),
            os.path.join(directory, stem + EXPECTATION_SUFFIX))


# --- the pinned checkout -------------------------------------------------------------------------


def _cache_root():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "rules-factory", "rules-corpus")


def _run(argv, cwd, what):
    env = dict(os.environ, DOTNET_NOLOGO="1", DOTNET_CLI_TELEMETRY_OPTOUT="1")
    try:
        return subprocess.run(argv, cwd=cwd, env=env, capture_output=True)
    except OSError as error:
        raise Unavailable(f"{what}: cannot run {argv[0]} ({error})")


def _git(checkout, *args):
    result = _run(["git", "-C", checkout, *args], checkout, "rules-corpus checkout")
    return result.returncode, result.stdout.decode("utf-8", "replace").strip()


def _problem(checkout):
    """Why `checkout` is not the pinned rules-corpus, or None when it is."""
    code, head = _git(checkout, "rev-parse", "HEAD")
    if code != 0:
        return f"{checkout} is not a git checkout"
    if head != COMMIT:
        return f"{checkout} is at {head}, not the pinned {COMMIT}"
    code, changes = _git(checkout, "status", "--porcelain", "--untracked-files=no")
    if code != 0 or changes:
        return f"{checkout} has modified tracked files:\n{changes}"
    return None


def checkout():
    """The path of a built checkout of rules-corpus at COMMIT, fetching and building it if absent."""
    root = _cache_root()
    target = os.path.join(root, COMMIT)
    os.makedirs(root, exist_ok=True)
    with open(os.path.join(root, COMMIT + ".lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not os.path.isdir(target):
            staging = tempfile.mkdtemp(prefix=".fetch-", dir=root)
            try:
                for args in (("init", "-q"), ("fetch", "-q", "--depth", "1", REPOSITORY, COMMIT),
                             ("checkout", "-q", "--detach", "FETCH_HEAD")):
                    code, output = _git(staging, *args)
                    if code != 0:
                        raise Unavailable(f"cannot fetch rules-corpus {COMMIT} from {REPOSITORY} "
                                          f"(git {args[0]}): {output}")
                os.rename(staging, target)
            finally:
                shutil.rmtree(staging, ignore_errors=True)
        problem = _problem(target)
        if problem:
            raise Unavailable(f"the rules-corpus checkout is not the pinned one: {problem}. Delete "
                              f"{target} and it is fetched again.")
        built = os.path.join(target, ".rules-factory-built")
        if not os.path.isfile(built):
            result = _run(["dotnet", "build", CLI_PROJECT, "-c", "Release", "-v", "q", "--nologo"],
                          target, "rules-corpus build")
            if result.returncode != 0:
                raise Unavailable(f"rules-corpus {COMMIT} does not build here:\n"
                                  f"{(result.stdout + result.stderr).decode('utf-8', 'replace')}")
            with open(built, "w") as handle:
                handle.write(COMMIT + "\n")
    return target


def run(*args):
    """`rules-corpus <args> --json` from the pinned checkout: (exit code, parsed JSON or None, stderr)."""
    where = checkout()
    result = _run(["dotnet", "run", "--no-build", "--project", CLI_PROJECT, "-c", "Release", "--",
                   *args, "--json"], where, "rules-corpus")
    try:
        document = json.loads(result.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        document = None
    if result.returncode not in (0, 1, 3) or (document is None and result.returncode == 0):
        raise Unavailable(f"rules-corpus {' '.join(args[:1])} exited {result.returncode}:\n"
                          f"{(result.stdout + result.stderr).decode('utf-8', 'replace')}")
    return result.returncode, document, result.stderr.decode("utf-8", "replace")


# --- one corpus ----------------------------------------------------------------------------------


def expectation(path, data):
    """The check names the expectation file at `path`, whose bytes are `data`, pins, in its order."""
    try:
        document = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Refused(f"{path} is not readable JSON ({error})")
    names = document.get("expectNotVerified") if isinstance(document, dict) else None
    if (not isinstance(document, dict) or set(document) != {"expectNotVerified"}
            or not isinstance(names, list)
            or not all(isinstance(n, str) and n and n.strip() == n and "," not in n for n in names)
            or len(set(names)) != len(names)):
        raise Refused(f"{path} must be exactly {{\"expectNotVerified\": [<check name>, ...]}}, each "
                      f"name as `rules-corpus verify` prints it, once")
    return names


def _stored_sources(definition, where):
    """The relative path of every source the definition stores (the bytes rules-corpus will read)."""
    sources = definition.get("sources") if isinstance(definition, dict) else None
    if not isinstance(sources, list):
        raise Refused(f"{where} declares no sources list")
    paths = []
    for source in sources:
        if isinstance(source, dict) and source.get("stored", True) is not False:
            path = source.get("path")
            if not isinstance(path, str) or not path or path.startswith("/") or ".." in path.split("/"):
                raise Refused(f"{where} stores a source at {path!r}, which is not a relative path")
            paths.append(path)
    return paths


def carried(corpus_path):
    """Every file building the corpus at `corpus_path` reads, relative to its directory: the
    definition, the expectation and each stored source (the corpus file among them). What an engine
    carries in `corpus/` for a corpus is exactly this."""
    definition_path, expectation_path = companions(corpus_path)
    try:
        with open(definition_path, encoding="utf-8") as handle:
            definition = json.load(handle)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Refused(f"{definition_path} cannot be read as a build definition ({error})")
    return [os.path.basename(definition_path), os.path.basename(expectation_path),
            *_stored_sources(definition, definition_path)]


def _report(document, stderr):
    if not isinstance(document, dict):
        return stderr.strip()
    lines = [f"  {c.get('outcome')}: {c.get('name')}: {c.get('detail')}"
             for c in document.get("checks") or [] if isinstance(c, dict) and c.get("outcome") != "ok"]
    pin = document.get("expectedNotVerified")
    if isinstance(pin, dict) and not pin.get("met"):
        if pin.get("unexpected"):
            lines.append(f"  not verified but not expected: {', '.join(pin['unexpected'])}")
        if pin.get("missing"):
            lines.append(f"  expected not verified but not reported so: {', '.join(pin['missing'])}")
    error = document.get("error") if isinstance(document.get("error"), dict) else {}
    for problem in error.get("problems") or []:
        if isinstance(problem, dict):
            lines.append(f"  {problem.get('path')}: {problem.get('reason')}")
    return "\n".join(lines) or error.get("message") or stderr.strip()


def build_and_verify(corpus_path, read):
    """Build the corpus whose file is `corpus_path` from its committed definition, and verify it.

    `read(path) -> bytes` reads each file the build takes in, so the caller's bounds hold on every
    one of them. Returns {"baselines": {sourceId: {...}}, "files": {name: bytes}}: each baseline as
    the built manifest records it (`contentHash` is the named artifact's SHA-256 hex, `path` where
    that artifact is stored), and every file the build read, by its path relative to the corpus
    file's directory -- what an engine must carry to build it again.
    """
    directory = os.path.dirname(corpus_path)
    definition_path, expectation_path = companions(corpus_path)
    if not os.path.isfile(definition_path):
        raise Refused(f"{definition_path} does not exist: a corpus is built by rules-corpus from the "
                      f"build definition committed beside it (#558)")
    definition_bytes = read(definition_path)
    try:
        definition = json.loads(definition_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Refused(f"{definition_path} is not readable JSON ({error})")
    if not os.path.isfile(expectation_path):
        raise Refused(f"{expectation_path} does not exist: every corpus declares the checks it accepts "
                      f"as not verified, and {{\"expectNotVerified\": []}} accepts none (#558)")
    expectation_bytes = read(expectation_path)
    expected = expectation(expectation_path, expectation_bytes)

    files = {os.path.basename(definition_path): definition_bytes,
             os.path.basename(expectation_path): expectation_bytes}
    sources = _stored_sources(definition, definition_path)
    for relative in sources:
        files[relative] = read(os.path.join(directory, *relative.split("/")))

    identity = hashlib.sha256()
    for part in (REPOSITORY, COMMIT, _cache_root(), definition_bytes, expectation_bytes,
                 *(item for relative in sources for item in (relative, files[relative]))):
        data = part if isinstance(part, bytes) else part.encode("utf-8")
        identity.update(len(data).to_bytes(8, "big") + data)
    key = identity.hexdigest()
    if key in _VERIFIED:
        return dict(_VERIFIED[key], files=files)

    with tempfile.TemporaryDirectory(prefix="factory-corpus-") as scratch:
        with open(os.path.join(scratch, "corpus.build.json"), "wb") as handle:
            handle.write(definition_bytes)
        for relative in sources:
            target = os.path.join(scratch, *relative.split("/"))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as handle:
                handle.write(files[relative])

        code, document, stderr = run("build", "--dir", scratch)
        if code != 0:
            raise Refused(f"rules-corpus build refused {definition_path} (exit {code}):\n"
                          f"{_report(document, stderr)}")
        argv = ["verify", scratch, "--rebuild"]
        if expected:
            argv += ["--expect-not-verified", ",".join(expected)]
        code, document, stderr = run(*argv)
        if code != 0:
            raise Refused(f"NOT VERIFIED -- rules-corpus verify --rebuild of {definition_path} exited "
                          f"{code}, under the expectation {expectation_path} "
                          f"({', '.join(expected) or 'nothing unverified'}):\n{_report(document, stderr)}")
        with open(os.path.join(scratch, "corpus.json"), encoding="utf-8") as handle:
            manifest = json.load(handle)

    artifacts = {a["id"]: a for a in manifest.get("artifacts") or []}
    baselines = {}
    for baseline in manifest.get("baselines") or []:
        artifact = artifacts[baseline["artifact"]]
        baselines[baseline["sourceId"]] = {
            "sourceId": baseline["sourceId"],
            "contentHash": artifact["digest"].split(":", 1)[1],
            "hashDerivation": baseline["hashDerivation"],
            "asOf": baseline.get("asOf"),
            "path": artifact.get("path"),
        }
    result = {"baselines": baselines, "expectNotVerified": expected,
              "contentDigest": manifest.get("contentDigest")}
    _VERIFIED[key] = result
    return dict(result, files=files)
