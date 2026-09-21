"""M1 of #3: intake. Open a map package, prove the corpus in hand is the one it was mapped from.

An engine is only as right as the correspondence between its map and its corpus, so nothing
is scaffolded until seven things are shown, in this order, and any one that is not shown is a
refusal rather than a warning:

  1. **The package is a map package.** A `.nupkg` built by `tools/pack-map.py` (0015): its
     `build/<id>.props` declares exactly one `RulesFactoryMap` item, and the map, manifest,
     `ConsumerChecker` and `Verification` record that item names are all inside the archive. A package without its
     checker (pre-2.0.0 backgammon, or a hand-built zip) is not one an engine's gate can use
     (#51), so it is refused, not tolerated. The checker's bytes are read so provenance can
     record their digest; they are never run (below).
  2. **The map is in a schemaVersion this factory reads.** The supported set is
     `SCHEMA_VERSIONS` in the factory's own `tools/check-map.py`, not a copy kept here. A map in
     any other version is refused, naming the versions that would be accepted.
  3. **The package binds the artifacts its publish gate verified.** Its decision-0048
     verification record names the map, manifest and packaged checker by SHA-256 and names every
     corpus the map cites by sourceId, hashDerivation and contentHash. Those artifact digests are
     compared with the actual package members; a legacy package with no binding is refused.
  4. **Every cited corpus may be committed and published, and is verifiable here.** Its
     `licence` is public domain or an admitted open licence (0028), and its `verification` is
     `committed-copy` (0013). A local-copy corpus is NOT VERIFIED.
  5. **Every resolved corpus file is the exact identity this package was verified against.**
     The map's principal `baseline` agrees with the manifest; each supplied file is recomputed
     under the one canonical `hashDerivation` table, must equal its manifest contentHash, and
     must equal the package verification record's contentHash for that same sourceId. Unknown
     derivations and malformed declared digests fail closed.
  6. **The corpora agree on whether the engine may draw random values** (0019): `randomness` is
     `none` or `seeded`. A package whose manifest predates the field declares nothing, and is
     refused rather than read as `none`: the answer is the corpus's, and a default would be the
     factory's.
  7. **The factory's own checker passes, in its consumer phase**, on the packaged map and
     manifest. Before any overlay exists this is the map exactly as published, so a failure
     here means the map does not hold under the checks its engine will run, and no engine
     should be built on it.

**A package is data, never code (0016).** Nothing here executes, imports or `exec`s a byte
that came out of a package: the map and manifest are parsed as JSON, and the checker that
judges them is `tools/check-map.py` beside this factory, loaded from the factory's own
checkout and versioned with it. The package's `ConsumerChecker` is for the engine's build,
which chose that package by exact version and lock-file hash. The factory has chosen nothing
yet when it opens a package, so running what the package names would hand the package the
privileges of whoever runs the factory before a single claim in it had been checked.

**Nothing is read without a limit (#187, #229).** All seven checks above run on bytes intake
already holds, so the size of what it takes in is the one thing it must decide before it has
verified anything. Every read is bounded before it starts, and by a cap named here:

  * a package is refused over `MAX_PACKAGE_BYTES`, whatever its source -- a download is stopped
    and deleted at that many bytes as it streams, and a `.nupkg` named on the command line or
    found in the NuGet global packages folder is measured before it is hashed or opened;
  * an archive is refused over `MAX_ARCHIVE_ENTRIES` entries, before any member is read;
  * a member is refused unread over `MAX_MEMBER_BYTES` uncompressed, or over a compression ratio
    of `MAX_COMPRESSION_RATIO`;
  * a corpus is refused over `MAX_CORPUS_BYTES`, measured before it is opened and counted again
    as it is read in chunks.

The package and the corpus the operator names are theirs, so this is about not exhausting their
machine, not about trust.

**A nuspec or props that declares a DTD is refused before it is parsed (#210).** The size caps
bound the bytes intake reads, not what an XML parser makes of them: `xml.etree` expands internal
entities, so a nuspec of a few kilobytes can declare its way to gigabytes inside the parser. A
DTD is a small instruction set, and admitting one is admitting a little code (0016); nothing
`tools/pack-map.py` builds carries one, so a document type declaration is refused outright rather
than its expansion bounded.

What intake cannot do: tell whether the map is *right* about the corpus (the publish gate's
locator checkers and review did that), or whether a newer version of the package exists.

Standard library only.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import re
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
import xml.parsers.expat
import zipfile

FLAT_CONTAINER = "https://api.nuget.org/v3-flatcontainer"

# What each `hashDerivation` covers, and how to recompute it from the file an engine commits.
#
# Both derivations in use today are SHA-256 over the file's bytes exactly as retrieved from
# the manifest's `retrievedFrom`; their names differ because the *bytes* differ from what a
# reader might assume, and that is the whole point of naming a derivation (corpus-map.md):
#
#   * ecfr-versioner-xml -- the XML document the eCFR versioner API serves for the part and
#     date, not the rendered HTML or the printed volume (examples/faa-part-107/README.md);
#   * gutenberg-plain-text-including-boilerplate -- the Project Gutenberg `.txt.utf-8`
#     including its licence header and footer, not the work text alone
#     (examples/hoyle-backgammon/README.md, finding 6).
#
# A derivation that needs normalisation (stripping boilerplate, canonicalising XML) gets its
# own function here; it must never be approximated by the raw-bytes one.
#
# This is the only table. Every engine's gate (recipe/engine-gate.py, `posture`) imports it from
# the copy of this file produce vendors at scripts/factory/intake.py, so a derivation admitted here
# is one every engine's gate can recompute (#106). Keep this module importable standalone, standard
# library only, from that directory.
def _sha256_of_bytes(data):
    return hashlib.sha256(data).hexdigest()


HASH_DERIVATIONS = {
    "ecfr-versioner-xml": _sha256_of_bytes,
    "gutenberg-plain-text-including-boilerplate": _sha256_of_bytes,
    # SHA-256 over the committed page-marked text, byte for byte -- which is *not* what was
    # retrieved: WotC publishes a PDF, and examples/srd-52-combat/extract.py derives the text
    # from it with pdftotext 24.02.0 and a `{N}` marker per page. The raw-bytes function is exact
    # here because the committed file is the derivation's output; the PDF's own digest is the
    # manifest's `sourcePdf.sha256`, and `extract.py --check` holds the two together.
    "srd-5.2.1-pdftotext-24.02.0-page-marked": _sha256_of_bytes,
}
SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
VERIFICATION_FORMAT = 1

# What a manifest may declare as a corpus's `randomness` (decision 0019). `seeded`: an engine may
# draw, and only through RulesKernel.Randomness's seeded, replayable source.
RANDOMNESS = ("none", "seeded")

# Decision 0028: the factory admits a corpus only when its licence permits committing and publishing
# its text and its map. The class is read from the leading identifier of the manifest's `licence`
# (before any whitespace, `;`, `,` or closing `.`): `public-domain`, or a `public-domain-` form that
# says whose (`public-domain-us-government`), is public domain; an identifier in OPEN_LICENCES is open.
# Anything else, a missing `licence` included, is neither, and is refused. An open licence is added
# here only with a decision that admits it.
PUBLIC_DOMAIN = "public-domain"
OPEN_LICENCES = ("CC-BY-4.0", "CC0-1.0")
LICENCE_IDENTIFIER = re.compile(r"\A([A-Za-z0-9][A-Za-z0-9.-]*?)\.?(?=[\s;,]|\Z)")

# The factory's own checker: tools/check-map.py, one directory above this package. It is a
# hyphenated script rather than a module, so it is loaded by path, once, on first use.
CHECKER_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "check-map.py")
_checker_module = None

PACKAGE_REF = re.compile(r"^(?P<id>[A-Za-z0-9_.-]+)@(?P<version>[0-9A-Za-z.+-]+)$")
THIS_DIR = "$(MSBuildThisFileDirectory)"

# How much of a package intake will take in before it has verified anything (#187). Every check
# below -- the digest, the props, the schema version, the consumer phase -- happens after the
# bytes are already here, so a package or a mirror that is hostile or merely broken could
# exhaust memory or disk before a single claim in it had been read. These bound that window.
#
# The numbers are sized off what a map package this factory builds actually weighs, with room
# for maps far larger than any written yet. Packing examples/ today:
#
#   srd-52-combat  235 KB, largest member map/corpus-map.json at 108 KB
#   faa-part-107   205 KB, largest member tools/check-map.py  at 105 KB
#   hoyle-backgammon 185 KB, same checker
#
# and every member deflates by at most 5.1x (the maps; the checker 3.7x, the XML and props under
# 3x). pack-map.py stores rather than deflates, so packages built here sit at ratio 1.0; a
# package repacked by another tool will not.
#
# They are constants, not options. This is a refusal boundary, and a limit an operator can raise
# is one an attacker's README can tell them to raise ("if intake refuses, set the cap higher").
# A real map that outgrows these wants a considered change here, not a flag at the call site.
#
# MAX_ARCHIVE_ENTRIES and MAX_CORPUS_BYTES are #229's: the first two caps bounded the bytes of a
# package and of one member, and left the *number* of members and the corpus unbounded.
#
#   * entries -- every package pack-map.py builds holds exactly ten members, and that number is
#     the package layout's, not the map's: it does not grow with the map, its entries, or the
#     number of corpora it cites. 1024 is a hundredfold of a count that does not vary, and it is
#     what bounds the central directory MAX_PACKAGE_BYTES alone would let hold over a million
#     entries -- each of which is a ZipInfo in memory before any member has been looked at.
#   * corpus -- the largest corpus committed here is examples/hazmat-172-table/section-172.101.xml
#     at 2.8 MiB (srd-5.2.1.txt is 1.3 MiB, hoyle.txt 723 KiB). 64 MiB is ~23x that, and is
#     deliberately the same number as MAX_PACKAGE_BYTES: both bound a whole file the operator
#     names, read into memory before anything about it has been verified. A corpus is text a
#     person reads and a map cites by locator, so a corpus that outgrows this wants the same
#     considered change the other caps do.
MAX_PACKAGE_BYTES = 64 * 1024 * 1024      # ~280x the largest package this factory builds
MAX_ARCHIVE_ENTRIES = 1024                # ~100x the ten members every package here holds
MAX_MEMBER_BYTES = 8 * 1024 * 1024        # ~75x the largest member; a map is JSON, not media
MAX_COMPRESSION_RATIO = 100               # real members reach 5.1x; a zip bomb reaches 1000x
MAX_CORPUS_BYTES = 64 * 1024 * 1024       # ~23x the largest corpus committed here
DOWNLOAD_CHUNK = 1024 * 1024              # also the chunk a .nupkg is hashed and a corpus read in


class Refused(Exception):
    """Intake did not pass. Nothing is produced."""


class Usage(Exception):
    """The inputs are not usable at all (missing file, unreadable archive)."""


class Intake:
    """Everything later milestones read, established as true of each other."""

    def __init__(self, **fields):
        self.__dict__.update(fields)


def _note(log, message):
    if log is not None:
        print(message, file=log, flush=True)


# --- locating the package ----------------------------------------------------------------


def _global_packages_folder():
    return os.environ.get("NUGET_PACKAGES") or os.path.join(os.path.expanduser("~"), ".nuget", "packages")


def sha256_of_file(path):
    """The file's SHA-256, read a chunk at a time: a .nupkg is never held whole in memory."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(DOWNLOAD_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url, target):
    """Stream `url` to `target`, hashing as it goes; refuse past MAX_PACKAGE_BYTES (#187).

    Hashed while streaming rather than re-read afterwards, and capped while streaming rather
    than checked afterwards: by the time a whole `response.read()` had returned, the memory or
    the disk is already spent. What is written before the cap is reached is removed, so a
    refusal leaves no half a package behind for anything else to pick up.
    """
    digest, total = hashlib.sha256(), 0
    try:
        with urllib.request.urlopen(url, timeout=60) as response, open(target, "wb") as handle:
            for chunk in iter(lambda: response.read(DOWNLOAD_CHUNK), b""):
                total += len(chunk)
                if total > MAX_PACKAGE_BYTES:
                    raise Refused(f"{url} is larger than {MAX_PACKAGE_BYTES} bytes, the most intake will "
                                  f"download; nothing in a package is verified until it is here, so the "
                                  f"download is stopped and the partial file removed")
                digest.update(chunk)
                handle.write(chunk)
    except BaseException as error:
        with contextlib.suppress(OSError):
            os.remove(target)
        if isinstance(error, OSError):
            raise Usage(f"cannot fetch {url}: {error}")
        raise
    return digest.hexdigest()


def _package_in_hand(path):
    """(path, its SHA-256) for a `.nupkg` already on this machine, refused over the cap (#229).

    A download is bounded as it streams; a package named on the command line or found in the
    NuGet global packages folder arrives past that point, and was bounded by nothing at all. It
    is no more verified for having a path: nothing has read a byte of it yet, and the very next
    things intake does are hash it whole and hand it to `zipfile`, which reads its central
    directory. So it is measured first, by `os.stat`, and refused before it is opened.

    Measuring rather than reading is the point: the refusal costs one stat, and the file the cap
    turns away is never read at all.
    """
    try:
        size = os.path.getsize(path)
    except OSError as error:
        raise Usage(f"cannot read package {path}: {error}")
    if size > MAX_PACKAGE_BYTES:
        raise Refused(f"{path} is {size} bytes, over the {MAX_PACKAGE_BYTES} a package intake reads "
                      f"may be; nothing in a package is verified until it is here, so it is refused "
                      f"unread")
    return path, sha256_of_file(path)


def resolve_package(spec, download_dir, log=None):
    """(`.nupkg` path, its SHA-256) for `spec`: a file path, or `Id@Version` from the cache or nuget.org."""
    if os.path.isfile(spec):
        return _package_in_hand(os.path.abspath(spec))
    match = PACKAGE_REF.match(spec)
    if not match:
        raise Usage(f"--package {spec!r} is neither a .nupkg file nor Id@Version")
    lower_id, version = match["id"].lower(), match["version"].lower()
    name = f"{lower_id}.{version}.nupkg"
    cached = os.path.join(_global_packages_folder(), lower_id, version, name)
    if os.path.isfile(cached):
        _note(log, f"package {spec} from the NuGet global packages folder: {cached}")
        return _package_in_hand(cached)
    url = f"{FLAT_CONTAINER}/{lower_id}/{version}/{name}"
    target = os.path.join(download_dir, name)
    _note(log, f"package {spec} from {url}")
    return target, _download(url, target)


# --- reading the package -----------------------------------------------------------------


def _props_path(ref):
    """`$(MSBuildThisFileDirectory)../map/x.json` -> `map/x.json`, relative to the archive root."""
    if not isinstance(ref, str) or not ref.startswith(THIS_DIR):
        raise Refused(f"RulesFactoryMap path {ref!r} is not relative to $(MSBuildThisFileDirectory)")
    joined = os.path.normpath(os.path.join("build", ref[len(THIS_DIR):].replace("\\", "/")))
    if joined.startswith(".."):
        raise Refused(f"RulesFactoryMap path {ref!r} leaves the package")
    return joined.replace(os.sep, "/")


def _read_member(archive, name):
    """One member's bytes, refusing an oversized or over-compressed one *before* reading it (#187).

    This runs on every member intake reads, whatever the package's provenance: a downloaded one
    is capped on the way in, but one named on the command line or taken from the NuGet cache is
    not, and either can carry a member that decompresses to more memory than the machine has.

    Two checks, then the read:

      * the declared uncompressed size, against MAX_MEMBER_BYTES;
      * the declared ratio, against MAX_COMPRESSION_RATIO -- a member can sit under the size cap
        and still be a bomb relative to the bytes intake paid for it.

    Both read the archive's own declarations, which the package controls, so checking them looks
    like trusting the attacker. What makes it sound is the reader underneath: `ZipFile.open`
    stops at the declared `file_size` and verifies the member's CRC-32, so a member that declares
    less than it holds does not hand back the extra -- it fails, and that failure is a refusal
    here rather than a traceback. A declaration can therefore only be an *over*statement, and an
    overstatement is refused above. The read is still asked for one byte past the declared size
    and checked, so the bound is stated here and does not rest on that reader's internals.
    """
    info = archive.getinfo(name)
    if info.file_size > MAX_MEMBER_BYTES:
        raise Refused(f"{name} declares {info.file_size} uncompressed bytes, over the {MAX_MEMBER_BYTES} "
                      f"a package member may be; it is refused unread")
    ratio = info.file_size / info.compress_size if info.compress_size else info.file_size
    if ratio > MAX_COMPRESSION_RATIO:
        raise Refused(f"{name} declares {info.file_size} bytes from {info.compress_size} compressed, a ratio "
                      f"of {ratio:.0f} over the {MAX_COMPRESSION_RATIO} a package member may be; it is "
                      f"refused unread")
    try:
        with archive.open(name) as member:
            data = member.read(info.file_size + 1)
    except (OSError, zipfile.BadZipFile) as error:
        raise Refused(f"{name} cannot be read as the {info.file_size} bytes it declares: {error}")
    if len(data) > info.file_size:
        raise Refused(f"{name} decompresses to more than the {info.file_size} bytes it declares; the size "
                      f"intake checked was not the size the member has")
    return data


class _DeclaresADocumentType(Exception):
    pass


def _refuse_document_type(*_):
    raise _DeclaresADocumentType()


def _xml(name, data):
    """A package member parsed as XML, refused if it declares a document type (#210).

    The declaration is found by expat itself rather than by searching the bytes for `<!DOCTYPE`:
    expat honours the document's own encoding, so a UTF-16 nuspec that a byte search would read
    past is seen here. The handler fires at the start of the declaration, before any entity in it
    is declared, let alone expanded, and raising from it stops the parse there. An entity
    declaration can only appear inside a DTD, so refusing the DTD refuses every entity with it;
    the entity handler is set as well so that stays true without resting on that rule.
    """
    scan = xml.parsers.expat.ParserCreate()
    scan.StartDoctypeDeclHandler = _refuse_document_type
    scan.EntityDeclHandler = _refuse_document_type
    try:
        scan.Parse(data, True)
    except _DeclaresADocumentType:
        raise Refused(f"{name} declares a document type (DTD); a map package is data, not code (0016), and "
                      f"a DTD's entities are instructions the parser would run, so it is refused unparsed")
    except xml.parsers.expat.ExpatError as error:
        raise Refused(f"{name} is not well-formed XML: {error}")
    return ET.fromstring(data)


def read_package(nupkg):
    try:
        archive = zipfile.ZipFile(nupkg)
    except (OSError, zipfile.BadZipFile) as error:
        raise Usage(f"{nupkg} is not a readable .nupkg: {error}")
    with archive:
        # #229: the entry count, before any member is read. MAX_PACKAGE_BYTES bounds the archive's
        # bytes and MAX_MEMBER_BYTES one member's, and between them sits an archive of a million
        # empty entries: each is a ZipInfo held in memory, and each name below is matched against
        # every one of them. `infolist()` is the central directory zipfile has already parsed, so
        # counting it reads nothing further, and the refusal happens before `_read_member` opens
        # anything. The count is of the records zipfile actually parsed, not of the number the
        # end-of-directory record declares, so it is a measurement rather than a claim the
        # package makes about itself.
        entries = archive.infolist()
        if len(entries) > MAX_ARCHIVE_ENTRIES:
            raise Refused(f"{nupkg} holds {len(entries)} entries, over the {MAX_ARCHIVE_ENTRIES} a map "
                          f"package may hold; every package this factory builds holds ten, so it is "
                          f"refused before any member is read")
        names = {info.filename for info in entries}
        nuspecs = [n for n in names if "/" not in n and n.endswith(".nuspec")]
        if len(nuspecs) != 1:
            raise Refused(f"{nupkg}: expected one root .nuspec, found {sorted(nuspecs) or 'none'}")
        metadata = _xml(nuspecs[0], _read_member(archive, nuspecs[0])).find("{*}metadata")
        package_id = metadata.findtext("{*}id") if metadata is not None else None
        version = metadata.findtext("{*}version") if metadata is not None else None
        if not package_id or not version:
            raise Refused(f"{nupkg}: the nuspec names no id and version")

        props_name = f"build/{package_id}.props"
        # NuGet matches the props name case-insensitively; so does this.
        props = [n for n in names if n.lower() == props_name.lower()]
        if not props:
            raise Refused(f"{package_id} {version} has no {props_name}, so it declares no "
                          f"RulesFactoryMap item and is not a map package (0015)")
        items = [e for e in _xml(props[0], _read_member(archive, props[0])).iter() if e.tag.endswith("RulesFactoryMap")]
        if len(items) != 1:
            raise Refused(f"{props_name} declares {len(items)} RulesFactoryMap items; a map package declares one")
        item = items[0].attrib
        for field in ("Include", "Manifest", "ConsumerChecker", "Verification"):
            if not item.get(field):
                detail = ("; packages published before decision 0048 are legacy/unbound and cannot "
                          "establish which corpus bytes their publish gate checked"
                          if field == "Verification" else "")
                raise Refused(f"{props_name}: the RulesFactoryMap item has no {field}{detail}")
        if item.get("PackageId") != package_id or item.get("PackageVersion") != version:
            raise Refused(f"{props_name} says {item.get('PackageId')} {item.get('PackageVersion')}; "
                          f"the nuspec says {package_id} {version}")

        parts = {}
        for field, label in (("Include", "map"), ("Manifest", "manifest"), ("ConsumerChecker", "checker"),
                             ("Verification", "verification")):
            path = _props_path(item[field])
            if path not in names:
                what = ("the consumer-phase checker (#51), so an engine built on it could not run the "
                        "checks its own overlay can change" if label == "checker" else
                        "its package verification record (0048)" if label == "verification" else f"its {label}")
                raise Refused(f"{package_id} {version} names {path} as {what}, and the package does not contain it")
            parts[label] = (path, _read_member(archive, path))
    return package_id, version, parts


def _json(label, raw):
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise Refused(f"the packaged {label} is not JSON: {error}")


# --- the corpus --------------------------------------------------------------------------


def licence_class(licence):
    """`public-domain` or `open` for a manifest `licence` the factory admits (0028); None for any other."""
    found = LICENCE_IDENTIFIER.match(licence) if isinstance(licence, str) else None
    identifier = found.group(1) if found else ""
    if identifier == PUBLIC_DOMAIN or identifier.startswith(PUBLIC_DOMAIN + "-"):
        return "public-domain"
    if identifier in OPEN_LICENCES:
        return "open"
    return None


def refuse_unadmitted_licence(corpus):
    """Refused unless the manifest corpus's `licence` is public domain or open (0028)."""
    licence = corpus.get("licence") if isinstance(corpus, dict) else None
    if licence_class(licence) is None:
        source_id = corpus.get("sourceId") if isinstance(corpus, dict) else None
        raise Refused(f"{source_id}'s manifest `licence` is {licence!r}, which is neither public domain "
                      f"(`{PUBLIC_DOMAIN}`, or `{PUBLIC_DOMAIN}-<whose>`) nor an open licence the factory admits "
                      f"({', '.join(OPEN_LICENCES)}): the factory admits only corpora whose licence permits "
                      f"committing and publishing their text and maps (docs/decisions/0028)")


def cited_corpora(document):
    """Every `sourceId` the map depends on: its envelope's, and every entry's locator's.

    The envelope's `corpus` is the map's **principal** corpus -- the one its `baseline` stamps --
    and it is a dependency like any other. Nothing else in the factory turns on which corpus
    occupies that field (0039).
    """
    cited = {document.get("corpus")} if isinstance(document, dict) else set()
    for item in document.get("entries") or []:
        locator = item.get("locator") if isinstance(item, dict) else None
        if isinstance(locator, dict) and locator.get("sourceId"):
            cited.add(locator["sourceId"])
    return {c for c in cited if isinstance(c, str)}


def bind_corpora(cited, corpora, corpus_paths):
    """`{sourceId: path}`, or Refused/Usage saying which corpus has no file and which file no corpus.

    One cited corpus and one file are bound to each other directly, which is what a single-corpus
    `--corpus` has always meant and keeps every existing invocation working whatever the file is
    called. Beyond one, a file is bound to the corpus whose manifest `committedPath` it is the
    basename of: the manifest already says where each corpus is committed, so nothing new is
    declared and nothing is guessed. A file matching no cited corpus, or two files matching one,
    is refused rather than resolved.
    """
    if len(cited) == 1 and len(corpus_paths) == 1:
        return {next(iter(cited)): corpus_paths[0]}
    wanted = {}
    for source_id in cited:
        committed = corpora.get(source_id, {}).get("committedPath")
        if not committed:
            raise Refused(f"the map cites {source_id!r} and its manifest entry declares no "
                          f"`committedPath`, so no supplied corpus file can be bound to it")
        wanted.setdefault(os.path.basename(str(committed)), []).append(source_id)
    for name, sources in sorted(wanted.items()):
        if len(sources) > 1:
            raise Refused(f"the manifest commits {', '.join(sorted(sources))} at the same file "
                          f"name {name!r}; a supplied corpus could not be bound to one of them")
    bound, unmatched = {}, []
    for path in corpus_paths:
        name = os.path.basename(path)
        if name not in wanted:
            unmatched.append(path)
            continue
        source_id = wanted[name][0]
        if source_id in bound:
            raise Refused(f"two corpus files are named {name!r}; {source_id} takes exactly one")
        bound[source_id] = path
    if unmatched:
        raise Usage(f"{', '.join(sorted(unmatched))}: named by no corpus this map cites "
                    f"(expected one of {', '.join(sorted(wanted))})")
    missing = sorted(cited - set(bound))
    if missing:
        raise Usage(f"the map cites {', '.join(missing)} and no --corpus was supplied for "
                    f"{'them' if len(missing) > 1 else 'it'}; every cited corpus is verified here")
    return bound


def verify_declared_corpus_digest(source_id, corpus, corpus_bytes, where):
    """Return the canonical digest after proving bytes equal the manifest declaration (0048)."""
    derivation = corpus.get("hashDerivation") if isinstance(corpus, dict) else None
    derive = HASH_DERIVATIONS.get(derivation)
    if derive is None:
        raise Refused(f"NOT VERIFIED -- no way to compute hashDerivation {derivation!r}; known: "
                      f"{', '.join(sorted(HASH_DERIVATIONS))}")
    expected = corpus.get("contentHash") if isinstance(corpus, dict) else None
    if not isinstance(expected, str) or SHA256_HEX.fullmatch(expected) is None:
        raise Refused(f"{source_id} declares malformed contentHash {expected!r}; expected 64 lower-case "
                      f"hexadecimal SHA-256 characters for {derivation}")
    actual = derive(corpus_bytes)
    if actual != expected:
        raise Refused(f"{where} is not {source_id} at its declared baseline: {derivation} gives {actual}, "
                      f"the manifest declares {expected}")
    return actual


def read_corpus(corpus_path):
    """The corpus's bytes, under MAX_CORPUS_BYTES, measured before the file is opened (#229).

    The corpus is held whole because every derivation in HASH_DERIVATIONS is over the whole file
    and the map's entries are located in it afterwards; the question is only how much of it intake
    will hold. `os.stat` answers that without opening anything, so a corpus over the cap is refused
    without a byte of it being read -- which is the difference between a refusal and the
    exhaustion the refusal exists to prevent.

    The read is then chunked and counted against the cap a second time. The stat is a measurement
    of the file a moment ago, and a file can grow between the stat and the read (an operator's own
    pipeline still writing it, a FIFO, a file another process appends to); the counter makes the
    bound hold on the bytes actually taken in rather than on the bytes that were there when they
    were counted.
    """
    try:
        size = os.path.getsize(corpus_path)
    except OSError as error:
        raise Usage(f"cannot read corpus {corpus_path}: {error}")
    if size > MAX_CORPUS_BYTES:
        raise Refused(f"{corpus_path} is {size} bytes, over the {MAX_CORPUS_BYTES} a corpus intake "
                      f"reads may be; it is refused unread")
    chunks, total = [], 0
    try:
        with open(corpus_path, "rb") as handle:
            for chunk in iter(lambda: handle.read(DOWNLOAD_CHUNK), b""):
                total += len(chunk)
                if total > MAX_CORPUS_BYTES:
                    raise Refused(f"{corpus_path} is over the {MAX_CORPUS_BYTES} bytes a corpus intake "
                                  f"reads may be; it grew past the {size} bytes it measured, and the "
                                  f"read is stopped where the cap is")
                chunks.append(chunk)
    except OSError as error:
        raise Usage(f"cannot read corpus {corpus_path}: {error}")
    return b"".join(chunks)


def verify_one(source_id, corpus, corpus_path):
    """(corpus, bytes) once this corpus is proved admissible (0028) and to be its own baseline."""
    refuse_unadmitted_licence(corpus)

    posture = corpus.get("verification")
    if posture != "committed-copy":
        raise Refused(f"NOT VERIFIED -- {source_id} is {posture!r}, not committed-copy (0013): an engine "
                      f"produced from it could not re-derive its baseline wherever it is built")

    randomness = corpus.get("randomness")
    if isinstance(randomness, bool) or randomness not in RANDOMNESS:
        raise Refused(f"{source_id} declares randomness {randomness!r}; a corpus declares none or seeded "
                      f"(0019), and a manifest without the field is refused, not read as none")

    corpus_bytes = read_corpus(corpus_path)
    verify_declared_corpus_digest(source_id, corpus, corpus_bytes, corpus_path)
    return corpus, corpus_bytes


def verify_corpora(document, manifest, corpus_paths):
    """Every corpus the map cites, each resolved through the manifest and hashed here (0039).

    The manifest is the authority for the set: a map may cite several corpora, and each one's
    bytes are pinned by its own manifest entry rather than by the envelope's single `baseline`.
    The envelope's stamp still has to agree with its own corpus's entry -- that is
    `check-map.py --only manifest`'s -- and it pins that corpus and no other.

    The hash is **recomputed here from the bytes in hand**, never read across from the manifest:
    the manifest is what says which bytes are wanted, not evidence that these are they.
    """
    if not isinstance(document, dict) or not isinstance(manifest, dict):
        raise Refused("the packaged map or manifest is not a JSON object")
    cited = cited_corpora(document)
    if not cited:
        raise Refused("the map cites no corpus")
    principal = document.get("corpus")
    if principal not in cited:
        raise Refused(f"the map's envelope names corpus {principal!r}, which is not a string this "
                      f"factory can resolve")
    declared = {}
    for source_id in sorted(cited):
        matches = [c for c in manifest.get("corpora") or []
                   if isinstance(c, dict) and c.get("sourceId") == source_id]
        if len(matches) != 1:
            raise Refused(f"the packaged manifest declares {source_id!r} {len(matches)} times; every "
                          f"corpus the map cites is declared exactly once")
        declared[source_id] = matches[0]

    bound = bind_corpora(cited, declared, list(corpus_paths))
    verified = []
    for source_id in sorted(cited):
        corpus, corpus_bytes = verify_one(source_id, declared[source_id], bound[source_id])
        verified.append({"sourceId": source_id, "corpus": corpus, "bytes": corpus_bytes,
                         "path": bound[source_id], "name": os.path.basename(bound[source_id])})

    # An engine has one randomness posture (0019) and nothing says whose it would be. Two corpora
    # that disagree are refused rather than resolved by taking the envelope's, which would be
    # behaviour invented for the principal corpus and 0039 declines to invent any.
    postures = {v["corpus"]["randomness"] for v in verified}
    if len(postures) > 1:
        raise Refused(f"the corpora this map cites declare {', '.join(sorted(postures))}; an engine "
                      f"draws random values as its corpus declares (0019) and these do not agree")
    return verified


# --- package/corpus relationship ----------------------------------------------------------


def _verification_digest(label, value):
    if not isinstance(value, str) or SHA256_HEX.fullmatch(value) is None:
        raise Refused(f"package verification {label} is {value!r}; a SHA-256 identity is 64 lower-case "
                      f"hexadecimal characters")
    return value


def read_verification_binding(parts, document, manifest):
    """Validate package members and declarations named by verificationFormat 1 (0048)."""
    record = _json("verification", parts["verification"][1])
    if not isinstance(record, dict) or record.get("verificationFormat") != VERIFICATION_FORMAT:
        found = record.get("verificationFormat") if isinstance(record, dict) else None
        raise Refused(f"package verificationFormat is {found!r}; this factory reads {VERIFICATION_FORMAT}")

    artifacts = record.get("artifacts")
    if not isinstance(artifacts, list):
        raise Refused("package verification artifacts is not a list")
    expected_roles = {"map", "manifest", "checker"}
    by_role = {}
    for item in artifacts:
        role = item.get("role") if isinstance(item, dict) else None
        if role not in expected_roles or role in by_role:
            raise Refused(f"package verification has invalid or duplicate artifact role {role!r}; expected "
                          f"exactly {', '.join(sorted(expected_roles))}")
        by_role[role] = item
    if set(by_role) != expected_roles:
        raise Refused(f"package verification artifact roles are {sorted(by_role)}; expected "
                      f"{sorted(expected_roles)}")
    for role in sorted(expected_roles):
        item = by_role[role]
        path, raw = parts[role]
        if item.get("path") != path:
            raise Refused(f"package verification {role}.path is {item.get('path')!r}; package props name {path!r}")
        expected = _verification_digest(f"{role}.sha256", item.get("sha256"))
        actual = hashlib.sha256(raw).hexdigest()
        if actual != expected:
            raise Refused(f"package verification {role}.sha256 is {expected}, but {path} is {actual}")

    cited = cited_corpora(document)
    records = record.get("corpora")
    if not isinstance(records, list):
        raise Refused("package verification corpora is not a list")
    by_source = {}
    for item in records:
        source_id = item.get("sourceId") if isinstance(item, dict) else None
        if not isinstance(source_id, str) or source_id in by_source:
            raise Refused(f"package verification has malformed or duplicate corpus sourceId {source_id!r}")
        by_source[source_id] = item
    if set(by_source) != cited:
        raise Refused(f"package verification corpus set is {sorted(by_source)}; map cites {sorted(cited)}")

    declarations = {}
    for item in ((manifest.get("corpora") or []) if isinstance(manifest, dict) else []):
        if isinstance(item, dict) and item.get("sourceId") in cited:
            source_id = item["sourceId"]
            if source_id in declarations:
                raise Refused(f"the packaged manifest declares {source_id!r} more than once")
            declarations[source_id] = item
    if set(declarations) != cited:
        raise Refused(f"packaged manifest corpus set is {sorted(declarations)}; map cites {sorted(cited)}")

    for source_id in sorted(cited):
        bound, declared = by_source[source_id], declarations[source_id]
        derivation = bound.get("hashDerivation")
        if derivation != declared.get("hashDerivation"):
            raise Refused(f"package verification {source_id}.hashDerivation is {derivation!r}; manifest declares "
                          f"{declared.get('hashDerivation')!r}")
        expected = _verification_digest(f"{source_id}.contentHash", bound.get("contentHash"))
        if expected != declared.get("contentHash"):
            raise Refused(f"package verification {source_id}.contentHash is {expected}; manifest declares "
                          f"{declared.get('contentHash')!r}")
    return record, by_source


def verify_resolved_corpora_binding(bound, verified):
    """Require intake-resolved corpus bytes to be the exact identities certified by the package."""
    actual_sources = {item["sourceId"] for item in verified}
    if actual_sources != set(bound):
        raise Refused(f"intake resolved corpora {sorted(actual_sources)} but package verification binds "
                      f"{sorted(bound)}")
    for item in verified:
        source_id = item["sourceId"]
        declaration = item["corpus"]
        actual = HASH_DERIVATIONS[declaration["hashDerivation"]](item["bytes"])
        expected = bound[source_id]["contentHash"]
        if actual != expected:
            raise Refused(f"{item['path']} resolves {source_id} as {actual}, but this package was verified "
                          f"against {expected}")


# --- the factory's checker ---------------------------------------------------------------


def checker():
    """The factory's own `tools/check-map.py`, imported in-process.

    In-process rather than as a child process: it is the factory's own code, standard library
    only, and a subprocess would add an interpreter, a timeout to choose and an exit code to
    translate. A factory checkout without it is broken rather than refusing a package, so its
    absence is a usage error.
    """
    global _checker_module
    if _checker_module is None:
        if not os.path.isfile(CHECKER_PATH):
            raise Usage(f"the factory's checker {CHECKER_PATH} is missing; intake cannot run without it")
        spec = importlib.util.spec_from_file_location("factory_check_map", CHECKER_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _checker_module = module
    return _checker_module


def check_contract(document):
    """The package's contract is declarative: a `schemaVersion` the factory's checker reads.

    There is no fallback to the package's own checker for a version the factory does not know.
    That fallback is exactly the path by which a package would become code again (0016).
    """
    supported = checker().SCHEMA_VERSIONS
    version = document.get("schemaVersion") if isinstance(document, dict) else None
    if isinstance(version, bool) or version not in supported:
        raise Refused(f"the map is schemaVersion {version!r}, and this factory's check-map.py reads "
                      f"schemaVersion {', '.join(map(str, supported))}; a map in another version needs a "
                      f"factory that reads it, not the package's own checker (0016)")
    return version


# --- the consumer phase ------------------------------------------------------------------


def run_consumer_checks(parts, log=None):
    """The factory's `check-map.py --phase consumer` on the packaged map and manifest.

    Only the map and manifest are written to the scratch directory. The checker is the
    factory's, so the package's `ConsumerChecker` bytes never reach the filesystem as a
    script, let alone an interpreter. The checker's report is captured and passed to `log`, so
    a refusal shows which check failed.
    """
    module = checker()
    output = io.StringIO()
    with tempfile.TemporaryDirectory(prefix="factory-intake-") as scratch:
        paths = {}
        for label in ("map", "manifest"):
            path, data = parts[label]
            target = os.path.join(scratch, *path.split("/"))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as handle:
                handle.write(data)
            paths[label] = target
        argv = [paths["map"], "--manifest", paths["manifest"], "--repo-root", scratch, "--phase", "consumer"]
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            try:
                code = module.main(argv)
            except SystemExit as stop:  # argparse exits rather than returning
                code = stop.code if isinstance(stop.code, int) else 2
    _note(log, output.getvalue().rstrip("\n"))
    if code != 0:
        raise Refused(f"the factory's check-map.py --phase consumer exited {code} on the packaged map")


# --- the whole of intake -----------------------------------------------------------------


def intake(package_spec, corpus_paths, log=None):
    with tempfile.TemporaryDirectory(prefix="factory-download-") as downloads:
        nupkg, nupkg_sha256 = resolve_package(package_spec, downloads, log)
        package_id, version, parts = read_package(nupkg)
    _note(log, f"--- intake: {package_id} {version}")
    document = _json("map", parts["map"][1])
    manifest = _json("manifest", parts["manifest"][1])
    verification, bound_corpora = read_verification_binding(parts, document, manifest)
    _note(log, f"package verificationFormat {verification['verificationFormat']}: map, manifest and checker "
               f"digests match package members")
    schema_version = check_contract(document)
    _note(log, f"map schemaVersion {schema_version}: read by this factory's check-map.py")
    if isinstance(corpus_paths, str):
        corpus_paths = [corpus_paths]
    corpora = verify_corpora(document, manifest, corpus_paths)
    verify_resolved_corpora_binding(bound_corpora, corpora)
    for verified in corpora:
        corpus = verified["corpus"]
        _note(log, f"corpus {corpus['sourceId']}: {corpus['hashDerivation']} {corpus['contentHash']} "
                   f"recomputed from {verified['path']}")
    _note(log, f"randomness {corpora[0]['corpus']['randomness']} (0019), agreed by all "
               f"{len(corpora)} cited corpus(es)")
    _note(log, "--- intake: the factory's check-map.py --phase consumer (the package's checker is not run)")
    run_consumer_checks(parts, log)
    return Intake(
        package_id=package_id, version=version, nupkg_sha256=nupkg_sha256,
        map=document, map_raw=parts["map"][1],
        manifest=manifest, manifest_raw=parts["manifest"][1],
        checker_raw=parts["checker"][1],  # hashed for provenance, never executed (0016)
        verification=verification, verification_raw=parts["verification"][1],
        part_paths={label: path for label, (path, _) in parts.items()},
        corpora=corpora,
        # The principal corpus: the one the map's envelope names and its `baseline` stamps. It is
        # a dependency like the others, and nothing turns on which corpus occupies the field
        # beyond the stamp having to agree with it (0039).
        corpus=next(v["corpus"] for v in corpora if v["sourceId"] == document.get("corpus")),
        randomness=corpora[0]["corpus"]["randomness"],
    )
