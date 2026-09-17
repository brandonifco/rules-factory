"""The engine's overlay: one file per entry, under `overlay/` (#247, decision 0015).

Decision 0015 gives an engine three fields per entry -- `status`, `implementedIn`, `tests` -- and
decision 0027 adds its owner's `rulings` and `declines` beside them. That is unchanged here. What
moves is where those bytes live.

Until #247 they lived in one object, `corpus-map.overlay.json`, keyed by entry id. Every entry an
engine implemented appended to it, so **two entry branches cut from the same commit always
conflict in it**: measured on tax-121-principal-residence on 2026-09-17, six entries built in
parallel each had to hand-merge that file. It was the last file two entry branches were guaranteed
to collide in (#242); the backlog left the engine in #243, and the remaining generated files carry
per-entry regions a merge resolves.

So the overlay is a directory:

    overlay/<entry id>.json     the one entry's item, exactly the object that used to be the
                                value under `"<entry id>"` in corpus-map.overlay.json

One entry, one file, named for the entry. An entry branch adds or changes its own file and no
other, so two of them merge with nothing to resolve. The file name is the correspondence, which is
what `entry_id` and `path_for` mean, and it is why `check_name` refuses an entry id that is not
one path segment: a file named for something else would be evidence attributed to an entry nobody
can find.

**Read in map order, never in directory order.** `load` walks the package map's entries and picks
up each one's file; only then does it add the files that name no entry of the map, so 0015 rule 1
-- "every overlay key names an entry in the package map" -- still refuses them by name, which is
what an entry renamed upstream is caught by. Two engines with the same files therefore merge to
the same bytes whatever `os.listdir` returns on either machine, and the `rulings` of decision 0027
are collected in map order rather than in the order somebody happened to append them.

**The migration** (`split`, `superseded_by_split`). An engine produced before #247 has
`corpus-map.overlay.json` and no `overlay/`. The next `produce` writes one file per key and then
`ownership.remove_retired` deletes the old file -- and deletes it **only when the files just
written carry the whole of it**: `superseded_by_split` parses the bytes it is about to delete and
requires them to equal, as JSON, exactly what `load` now reads back. An overlay that is not an
object of entry id -> item, or that holds anything the split does not reproduce, is **kept and
named**, and the engine's owner is told; nothing is rewritten and nothing is lost.

That is the same shape of rule #243's retirement draws and for the same reason: a deletion is
authorised by what the bytes are, never by what the path is called. It is a different witness
because the claim is different. The backlog was the factory's own output being dropped, so the
record saying the factory wrote those exact bytes is what authorised it. The overlay is the
engine's own evidence being *moved*, which the factory never wrote and cannot claim to have
written -- so what authorises that deletion is proof the content survives the move.

Standard library only; vendored into every engine as scripts/factory/overlay.py, because
generate.py, ownership.py, provenance.py and the gate's scripts/map-overlay.py all read it.
"""
import json
import os
import re

#: Where an engine's overlay lives, relative to the engine root.
DIRECTORY = "overlay"
SUFFIX = ".json"
#: The one file `overlay/` replaces. Retired by ownership.py, migrated by `split`.
RETIRED_NAME = "corpus-map.overlay.json"

#: An entry id that may name a file: one path segment, no separators, no `.` or `..`, nothing the
#: shell or a Windows filesystem reads specially. Map entry ids are kebab-case slugs, so this
#: refuses nothing any map has ever held; it is here so that a map that grew an id with a `/` in it
#: would be refused loudly instead of writing evidence outside the directory.
NAME = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]*\Z")


class OverlayError(Exception):
    """The overlay directory cannot be read, or an entry id cannot name a file."""


def check_name(entry_id):
    """Refuse an entry id that cannot be a file name under `overlay/`."""
    if not isinstance(entry_id, str) or not NAME.match(entry_id) or entry_id in (".", ".."):
        raise OverlayError(f"{entry_id!r} is not an entry id that can name a file under {DIRECTORY}/: an "
                           f"overlay file is named for exactly one entry, so the id must be one path "
                           f"segment of letters, digits, `.`, `-` and `_`")
    return entry_id


def path_for(entry_id):
    """The engine-relative POSIX path of `entry_id`'s overlay file."""
    return f"{DIRECTORY}/{check_name(entry_id)}{SUFFIX}"


def entry_id(relative):
    """The entry id an engine-relative overlay path names, or None when it is not one."""
    parts = relative.split("/")
    if len(parts) != 2 or parts[0] != DIRECTORY or not parts[1].endswith(SUFFIX):
        return None
    return parts[1][:-len(SUFFIX)] or None


def is_overlay_file(relative):
    """Whether `relative` is a file of the overlay directory: `overlay/<something>.json`."""
    return entry_id(relative) is not None


def files(root):
    """Every overlay file under `root`, as engine-relative POSIX paths, sorted.

    Sorted by path so that a caller with no map -- provenance, the gate -- has a deterministic
    order. `load` reorders into map order, which is the order the merge is read in.
    """
    directory = os.path.join(root, DIRECTORY)
    if not os.path.isdir(directory):
        return []
    found = []
    for name in os.listdir(directory):
        if name.endswith(SUFFIX) and os.path.isfile(os.path.join(directory, name)):
            found.append(f"{DIRECTORY}/{name}")
    return sorted(found, key=lambda p: p.encode("utf-8"))


def read_item(root, relative):
    """One overlay file's item. Raises OverlayError for bytes that are not a JSON object."""
    path = os.path.join(root, *relative.split("/"))
    try:
        with open(path, encoding="utf-8") as handle:
            item = json.load(handle)
    except (OSError, ValueError) as error:
        raise OverlayError(f"cannot read {relative}: {error}")
    return item


def load(root, package=None):
    """The overlay of the engine at `root`, as `{entry id: item}`.

    **In map order** when `package` is given: the map's entries first, each one's file if it has
    one, and then every file that names no entry of the map, sorted. Those last are what 0015 rule
    1 refuses by name (`map-overlay.py`, `generate.merge`), and they are in the result precisely so
    that the refusal still happens rather than a renamed entry's evidence disappearing quietly.

    Without `package` -- provenance, the backlog renderer before it has a map -- the order is the
    path order `files` gives.
    """
    items = {}
    for relative in files(root):
        found = entry_id(relative)
        if found is None:  # unreachable: `files` yields only overlay paths
            continue
        items[found] = read_item(root, relative)
    if package is None:
        return items
    ordered = {}
    for entry in package.get("entries") or []:
        found = entry.get("id") if isinstance(entry, dict) else None
        if isinstance(found, str) and found in items:
            ordered[found] = items[found]
    for found in sorted(items, key=lambda i: i.encode("utf-8")):
        if found not in ordered:
            ordered[found] = items[found]
    return ordered


def serialise(item):
    """One overlay file's bytes: the item, as `produce` writes it."""
    return (json.dumps(item, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def retired_path(root):
    """`root`'s pre-#247 `corpus-map.overlay.json`, if it has one."""
    path = os.path.join(root, RETIRED_NAME)
    return path if os.path.isfile(path) else None


def split(root):
    """Write `corpus-map.overlay.json`'s entries as `overlay/<id>.json`; the paths written.

    Returns [] when there is nothing to migrate: no old file, or an `overlay/` directory that
    already holds files (the engine has migrated, and the old file -- if it is still there -- is
    one `remove_retired` kept and named, not a source to split again).

    Writes only files that are not already there, so a re-run cannot overwrite an entry file the
    engine has since edited. It does not delete the old file: that is `ownership.remove_retired`'s,
    under the witness below, so every deletion the factory makes goes through one door.
    """
    path = retired_path(root)
    if path is None or files(root):
        return []
    try:
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
    except (OSError, ValueError) as error:
        raise OverlayError(f"cannot read {RETIRED_NAME} to split it into {DIRECTORY}/: {error}")
    if not isinstance(document, dict):
        raise OverlayError(f"{RETIRED_NAME} is not an object of entry id -> the fields an engine owns, so it "
                           f"cannot be split into one file per entry; fix it, or move it aside and write "
                           f"{DIRECTORY}/<entry id>{SUFFIX} yourself")
    written = []
    for key in document:
        relative = path_for(key)
        target = os.path.join(root, *relative.split("/"))
        if os.path.exists(target):
            continue
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as handle:
            handle.write(serialise(document[key]))
        written.append(relative)
    return sorted(written, key=lambda p: p.encode("utf-8"))


def superseded_by_split(root, relative, data):
    """Why `data` at `relative` is not carried by `overlay/`, or None when it is (the witness).

    `ownership.remove_retired` calls this before deleting `corpus-map.overlay.json`, and the
    engine's `tools/pr-policy.py` calls it on the base commit's bytes before admitting that
    deletion into a produce update: one rule, drawn in one place, so the run and the policy can
    never disagree about whether the content survived.

    The test is content, not pathname and not formatting: the bytes parse to a JSON object, and
    that object equals, key for key and value for value, what `load` now reads out of `overlay/`.
    Then deleting them drops nothing -- every byte of meaning is in the files beside it. Anything
    else is kept where it is and named, which is the whole of "a hand-edited overlay is kept and
    named, not silently rewritten".
    """
    try:
        document = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        return (f"it is not readable JSON ({error}), so nothing can show that {DIRECTORY}/ carries what it "
                f"says")
    if not isinstance(document, dict):
        return (f"it is not an object of entry id -> the fields an engine owns, so it is not an overlay "
                f"{DIRECTORY}/ could carry")
    try:
        current = load(root)
    except OverlayError as error:
        return f"{DIRECTORY}/ cannot be read ({error}), so nothing shows it carries what this file says"
    if current != document:
        missing = sorted(set(document) - set(current))
        changed = sorted(k for k in set(document) & set(current) if current[k] != document[k])
        extra = sorted(set(current) - set(document))
        why = "; ".join(part for part in (
            f"{DIRECTORY}/ has no file for {', '.join(missing)}" if missing else "",
            f"{', '.join(changed)} differ(s) from the file(s) beside it" if changed else "",
            f"{DIRECTORY}/ also holds {', '.join(extra)}, which this file does not" if extra else "",
        ) if part)
        return (f"{DIRECTORY}/ does not carry what it holds ({why}), so deleting it would drop evidence this "
                f"engine wrote")
    return None
