#!/usr/bin/env python3
"""Verify every evidence artifact wherever it lives, fetching what this checkout does not hold.

tools/check-evidence.py verifies the artifacts in the checkout. This verifies the same artifacts
through the lock's own account of where each one's bytes are, which is the same thing today --
every artifact's `archive` is null, meaning "in this repository" -- and stays correct if any of
them is ever moved to a content-addressed archive.

The distinction is the point. An artifact verified because it happened to be beside the checker
proves the checkout is intact. An artifact verified through the identifier the lock records
proves the bytes are the ones the lock names, from wherever they came, which is the claim a
reviewer with a clean checkout actually needs.

Nothing is moved today, and this file does not move anything. What it establishes is that moving
one would not weaken the verification: the fetched bytes are hashed before they are used, the
digest is the one in the lock, a mismatch is a failure rather than a cache miss, and the cache is
a temporary directory that does not survive the run (AGENTS.md section 4).

**Not Git LFS.** LFS makes the bytes a property of the clone, not of the artifact: a reviewer with
a partial fetch gets a pointer file that reads like a document, and there is no digest in the
repository to hold the bytes to. A content-addressed identifier plus the SHA-256 in the lock can
be checked by anyone with the bytes and no special client.

## How an artifact's `archive` is read

  null              the bytes are at `path` in this repository
  file:<absolute>   the bytes are at that path on this machine -- the scheme a test can exercise
                    without a network, and the one a mirror on a build machine would use
  https://<url>     the bytes are fetched over the network

Every scheme verifies the same way. An `archive` this file cannot resolve is a failure and never
a skip: an evidence check that quietly did not check is the defect this repository has twice
found in its own tools.

Usage:
  fetch-evidence.py --verify            verify every artifact the lock names
  fetch-evidence.py --verify --fetched  verify, and list what had to be fetched

Exit 0 when every artifact verified and at least one was examined; 1 otherwise; 2 on a usage
error.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import pathlib
import shutil
import sys
import tempfile
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location("check_evidence", ROOT / "tools" / "check-evidence.py")
_evidence = importlib.util.module_from_spec(_spec)
sys.modules["check_evidence"] = _evidence
_spec.loader.exec_module(_evidence)


def resolve(artifact: dict, root: pathlib.Path, cache: pathlib.Path) -> tuple[pathlib.Path, bool]:
    """The bytes of one artifact, and whether they had to be fetched."""
    where = artifact.get("archive")
    if where is None:
        return root / artifact["path"], False
    target = cache / hashlib.sha256(artifact["path"].encode()).hexdigest()
    if where.startswith("file:"):
        source = pathlib.Path(where[len("file:"):])
        if not source.is_file():
            raise FileNotFoundError(f"{where} names no file")
        shutil.copyfile(source, target)
    elif where.startswith("https://"):
        with urllib.request.urlopen(where, timeout=60) as response, open(target, "wb") as handle:
            shutil.copyfileobj(response, handle)
    else:
        raise ValueError(f"{where!r} is not an archive identifier this tool can resolve")
    return target, True


def verify(lock: dict, root: pathlib.Path, cache: pathlib.Path) -> tuple[list[str], int, list[str]]:
    """Problems, the number of artifacts examined, and the ones that were fetched."""
    problems, examined, fetched = [], 0, []
    for artifact in lock.get("artifacts") or []:
        path = artifact["path"]
        try:
            bytes_at, was_fetched = resolve(artifact, root, cache)
        except Exception as exc:  # noqa: BLE001 -- an unresolvable artifact is a failure, not a skip
            problems.append(f"{path}: {type(exc).__name__}: {exc}")
            continue
        if was_fetched:
            fetched.append(path)
        actual = _evidence.digest(bytes_at)
        if actual != artifact.get("sha256"):
            problems.append(f"{path}: the lock says sha256 {artifact.get('sha256')}, "
                            f"the bytes at {artifact.get('archive') or 'this repository'} "
                            f"hash to {actual}")
            continue
        examined += 1
    return problems, examined, fetched


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="fetch-evidence.py", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--verify", action="store_true", required=True,
                        help="verify every artifact the lock names, fetching what is elsewhere")
    parser.add_argument("--fetched", action="store_true", help="list what had to be fetched")
    parser.add_argument("--lock", default=str(_evidence.LOCK))
    args = parser.parse_args(argv)

    lock_path = pathlib.Path(args.lock)
    if not lock_path.exists():
        print(f"fetch-evidence.py: {lock_path} does not exist", file=sys.stderr)
        return 1
    lock = _evidence.load(lock_path)

    # A temporary cache, removed however this exits: the gate leaves the checkout as it found it.
    with tempfile.TemporaryDirectory(prefix="evidence-") as tmp:
        problems, examined, fetched = verify(lock, ROOT, pathlib.Path(tmp))

    for line in problems:
        print(f"  X  {line}")
    if problems:
        print(f"\n{len(problems)} evidence artifact(s) are not the bytes the lock names")
        return 1
    if examined == 0:
        print("the lock named no artifact -- this check proved nothing", file=sys.stderr)
        return 1
    if args.fetched:
        for path in fetched:
            print(f"  fetched  {path}")
    elsewhere = sum(1 for a in lock["artifacts"] if a.get("archive") is not None)
    print(f"{examined} evidence artifact(s) verified against the lock: "
          f"{examined - len(fetched)} from this repository, {len(fetched)} fetched "
          f"({elsewhere} artifact(s) live outside it)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
