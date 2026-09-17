#!/usr/bin/env python3
"""Every committed corpus map carries a review of its exact bytes (0017).

0014 measured what automation cannot see in a map: mechanical checks caught 1 of 15
comprehension errors and the engine's tests caught none, where a blind second mapping caught
10 or 11. Nothing in merge policy stood for that. This repository has one maintainer, so an
approval would be the author approving themself. What it can require instead is a record that
names the bytes it reviewed, and a check that the bytes on the branch are those bytes.

Beside each map, `review.json` holds one review per map file in that directory, keyed by file
name. Every review names `sha256`, the digest of the map it covers, and one `method`:

  `blind-second-mapping`  The 0014 procedure was run. `comparison` is the comparator's output
                          and `resolutions` the row-per-disagreement record, both paths beside
                          `review.json`. `compared` names the commit and digest of the map the
                          comparator read, and that commit must be the one the comparison
                          itself names. `sha256` is the map as corrected to the resolutions,
                          which is the map that is used; the two digests differ by exactly the
                          corrections.

  `independent-verdict`   A reviewer in a separate context read the map against the corpus.
                          `verdict` is their file, and it must itself name the same `sha256`,
                          so a verdict cannot be carried forward to bytes it never saw.

  `exemption`             No review was run, and the record says why. `exemption.kind` is
                          `non-semantic` (the change alters no entry's meaning -- a
                          reformatting, a typo in a note; `previousSha256` names the reviewed
                          map it departs from) or `legacy` (the map predates this gate and has
                          not been blind-mapped; `issue` names where that work is tracked).
                          Either needs a `reason`. Exemptions pass, and every one is printed,
                          so a silent pass is not available.

What this does not buy, stated here rather than in a commit message:

  * The check binds a review to bytes; it cannot tell whether the review was done. Editing a
    map and then pasting its new digest into `review.json` passes. What it prevents is doing
    the first without the second, and it makes the second a line in the diff that has to say
    which method it claims.
  * `non-semantic` is the author's claim. Nothing here compares the two versions.
  * The comparator's own reference is checked only against what its output names. No git is
    run, so a shallow checkout gives the same answer as a full one.

Usage: check-map-review.py [MAP ...] [--root DIR]
With no MAP, checks every examples/*/corpus-map*.json and examples/*/*/corpus-map*.json under
the repository root, the same globs scripts/validate.sh uses. The second is there because a
reconciled map cannot sit beside the map it reconciles: `pack-map.py` requires exactly one
corpus-map*.json in a packable directory, so trial 9's Map C lives in its blind-mapping/
subdirectory with its own review.json. A map one level down is still a committed map and still
carries a review of its bytes. Exit 0 if every map has a review of its current bytes and at
least one map was examined; 1 otherwise; 2 on a usage error.
"""
import argparse
import hashlib
import json
import pathlib
import re
import sys

REVIEW_FILE = "review.json"
METHODS = ("blind-second-mapping", "independent-verdict", "exemption")
EXEMPTION_KINDS = ("non-semantic", "legacy")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
ISSUE = re.compile(r"^(#\d+|https://github\.com/[^/\s]+/[^/\s]+/issues/\d+)$")
ROOT = pathlib.Path(__file__).resolve().parent.parent

WHAT_TO_DO = (
    "      A map's bytes changed without its review. Do one of:\n"
    "        - run a blind second mapping (docs/method.md) and record it as blind-second-mapping;\n"
    "        - have a reviewer in a separate context write a verdict naming the new sha256;\n"
    "        - if the change alters no entry's meaning, record an exemption of kind non-semantic\n"
    "          with previousSha256 and a reason.\n"
    "      See docs/decisions/0017-a-map-change-carries-a-review-of-its-bytes.md."
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, f"{path} does not exist"
    except (OSError, ValueError) as exc:
        return None, f"{path} is not readable JSON: {exc}"


def text(value):
    return isinstance(value, str) and value.strip() != ""


def check_method(review, base, digest):
    """Problems with one review's method-specific fields, beyond the digest."""
    method = review.get("method")
    problems = []
    if method not in METHODS:
        return [f"method is {method!r}; expected one of {', '.join(METHODS)}"]

    if method == "blind-second-mapping":
        for field in ("comparison", "resolutions"):
            if not text(review.get(field)):
                problems.append(f"blind-second-mapping needs {field}, a path beside {REVIEW_FILE}")
            elif not (base / review[field]).is_file():
                problems.append(f"{field} {review[field]} does not exist")
        compared = review.get("compared")
        if not isinstance(compared, dict) or not text(compared.get("commit")) \
                or not HEX64.match(str(compared.get("sha256", ""))):
            problems.append("blind-second-mapping needs compared.commit and compared.sha256, "
                            "the map the comparator read")
        elif text(review.get("comparison")) and (base / review["comparison"]).is_file():
            output, err = load_json(base / review["comparison"])
            named = (output or {}).get("reference", {}).get("commit") if isinstance(output, dict) else None
            if err:
                problems.append(err)
            elif named != compared["commit"]:
                problems.append(f"compared.commit is {compared['commit']}, but the comparison "
                                f"names reference commit {named!r}")

    elif method == "independent-verdict":
        if not text(review.get("verdict")):
            problems.append(f"independent-verdict needs verdict, a path beside {REVIEW_FILE}")
        else:
            verdict, err = load_json(base / review["verdict"])
            if err:
                problems.append(err)
            elif not isinstance(verdict, dict) or verdict.get("sha256") != digest:
                problems.append(f"verdict {review['verdict']} names sha256 "
                                f"{(verdict or {}).get('sha256') if isinstance(verdict, dict) else None!r}, "
                                f"not the map's {digest}")

    else:
        ex = review.get("exemption")
        if not isinstance(ex, dict):
            return ["exemption needs an exemption object with kind and reason"]
        if ex.get("kind") not in EXEMPTION_KINDS:
            problems.append(f"exemption.kind is {ex.get('kind')!r}; expected one of "
                            f"{', '.join(EXEMPTION_KINDS)}")
        if not text(ex.get("reason")):
            problems.append("exemption.reason is empty; an exemption says why")
        if ex.get("kind") == "legacy" and not ISSUE.match(str(ex.get("issue", ""))):
            problems.append("a legacy exemption names the issue that tracks the missing review "
                            "(#N or an issue URL)")
        if ex.get("kind") == "non-semantic":
            prev = str(ex.get("previousSha256", ""))
            if not HEX64.match(prev):
                problems.append("a non-semantic exemption names previousSha256, the reviewed "
                                "map it departs from")
            elif prev == digest:
                problems.append("previousSha256 equals the map's digest; nothing changed to exempt")
    return problems


def check(maps, root):
    """Print a line per map, and return (examined, failed, exempt)."""
    examined = failed = exempt = 0
    reviews_by_dir = {}
    for map_path in maps:
        examined += 1
        rel = map_path.relative_to(root) if map_path.is_relative_to(root) else map_path
        base = map_path.parent
        digest = sha256(map_path)

        if base not in reviews_by_dir:
            reviews_by_dir[base] = load_json(base / REVIEW_FILE)
        doc, err = reviews_by_dir[base]
        review = None
        if err is None:
            review = (doc.get("reviews") or {}).get(map_path.name) if isinstance(doc, dict) else None
            if review is None:
                err = f"{base / REVIEW_FILE} has no review for {map_path.name}"
        if err is not None:
            failed += 1
            print(f"  X  {rel}  sha256 {digest}\n      no review: {err}\n{WHAT_TO_DO}")
            continue

        recorded = review.get("sha256")
        if recorded != digest:
            failed += 1
            print(f"  X  {rel}  sha256 {digest}\n      stale review: {REVIEW_FILE} records "
                  f"{recorded!r}\n{WHAT_TO_DO}")
            continue

        problems = check_method(review, base, digest)
        if problems:
            failed += 1
            print(f"  X  {rel}  {review.get('method')}")
            for p in problems:
                print(f"      {p}")
            continue

        if review["method"] == "exemption":
            ex = review["exemption"]
            where = f" ({ex['issue']})" if ex.get("issue") else ""
            print(f"  EXEMPT  {rel}  {ex['kind']}{where}: {ex['reason']}")
            exempt += 1
        else:
            print(f"  ok  {rel}  {review['method']}")

    # A review naming a map that is not there is a record of nothing.
    for base, (doc, err) in reviews_by_dir.items():
        if err is None and isinstance(doc, dict):
            for name in sorted(doc.get("reviews") or {}):
                if not (base / name).is_file():
                    failed += 1
                    print(f"  X  {base / REVIEW_FILE} reviews {name}, which does not exist")
    return examined, failed, exempt


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("maps", nargs="*", help="corpus map files (default: examples/*/corpus-map*.json)")
    ap.add_argument("--root", default=str(ROOT), help="repository root for the default glob")
    args = ap.parse_args(argv)

    root = pathlib.Path(args.root).resolve()
    if args.maps:
        maps = [pathlib.Path(m).resolve() for m in args.maps]
        missing = [str(m) for m in maps if not m.is_file()]
        if missing:
            print(f"no such map: {', '.join(missing)}", file=sys.stderr)
            return 2
    else:
        maps = sorted(set(root.glob("examples/*/corpus-map*.json"))
                      | set(root.glob("examples/*/*/corpus-map*.json")))

    examined, failed, exempt = check(maps, root)
    if examined == 0:
        print("no corpus maps found -- this check proved nothing", file=sys.stderr)
        return 1
    if failed:
        print(f"\n{failed} problem(s) across {examined} map(s): not every map has a review of its current bytes")
        return 1
    print(f"{examined} map(s), each with a review of its current bytes ({exempt} by exemption)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
