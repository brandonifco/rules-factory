#!/usr/bin/env python3
"""Record a review verdict from the exact machine-readable packet the reviewer used.

    tools/record-verdict.py --pr 12 --packet /tmp/pr-12-abc.review.json \
        --reviewer semantic --verdict pass

Emitted by rules-factory as a managed file (decisions 0029 and 0049).

The review packet, not mutable pull-request state, says which commit was reviewed. This command
re-hashes the human packet and every bound entry packet, verifies the reviewed-tree source
identities against that exact Git commit, and then posts the verdict to that reviewed commit only.
The current PR head is consulted solely to report whether the evidence is stale for the gate.

Legacy Markdown-only packets are historical artifacts, not authorization to post a new gating
verdict. `--sha` remains only as a compatibility assertion: when supplied it must equal the
packet's reviewed commit and can never override it.

What this still cannot authenticate is which model/provider actually produced the verdict or
whether the fallback chain was tried in order. Those remain operator obligations.

Standard library only, plus `gh` (or `$RULES_ENGINE_GH`) and `git`.
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
POLICY = ".github/agent-policy.json"
SEMANTIC = "semantic"
PACKET_FORMAT = 1
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class Refused(Exception):
    """Something that must not be recorded. Nothing is posted."""


def gh(*args, check=True):
    command = [os.environ.get("RULES_ENGINE_GH", "gh"), *args]
    done = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                          cwd=ROOT, timeout=120)
    if check and done.returncode != 0:
        raise Refused(f"{' '.join(command)} failed: {done.stderr.strip() or done.stdout.strip()}")
    return done.stdout


def git(*args, check=True):
    done = subprocess.run(["git", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          cwd=ROOT, text=False)
    if check and done.returncode != 0:
        detail = done.stderr.decode("utf-8", "replace").strip() or done.stdout.decode("utf-8", "replace").strip()
        raise Refused(f"git {' '.join(args)} failed: {detail}")
    return done


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_manifest(path):
    manifest = pathlib.Path(path).expanduser().resolve()
    try:
        document = json.loads(manifest.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise Refused(f"review packet manifest is missing: {manifest}")
    except (OSError, ValueError) as error:
        raise Refused(f"review packet manifest cannot be read ({manifest}): {error}")
    if not isinstance(document, dict):
        raise Refused("review packet manifest must be a JSON object")
    if document.get("formatVersion") != PACKET_FORMAT:
        raise Refused(f"review packet format {document.get('formatVersion')!r} is not supported; "
                      f"format {PACKET_FORMAT} is required for newly recorded verdicts")
    return manifest, document


def exact_sha(value, field):
    if not isinstance(value, str) or not SHA40.fullmatch(value):
        raise Refused(f"review packet {field} must be one 40-character lowercase commit SHA")
    return value


def exact_digest(value, field):
    if not isinstance(value, str) or not SHA256.fullmatch(value):
        raise Refused(f"review packet {field} must be one lowercase sha256 digest")
    return value


def safe_file(name, field):
    if not isinstance(name, str) or not name or pathlib.PurePosixPath(name).name != name or name in (".", ".."):
        raise Refused(f"review packet {field} must be a file name beside the manifest, not a path")
    return name


def verify_file(directory, item, field):
    if not isinstance(item, dict) or set(item) != {"file", "sha256"}:
        raise Refused(f"review packet {field} has an unknown shape")
    name = safe_file(item.get("file"), f"{field}.file")
    expected = exact_digest(item.get("sha256"), f"{field}.sha256")
    path = directory / name
    try:
        actual = digest(path.read_bytes())
    except OSError as error:
        raise Refused(f"bound {field} file {name} cannot be read ({error})")
    if actual != expected:
        raise Refused(f"bound {field} file {name} hashes to {actual}, not manifest digest {expected}")
    return path


def verify_artifacts(directory, artifacts):
    if not isinstance(artifacts, list):
        raise Refused("review packet artifacts must be a list")
    seen_files = set()
    seen_entries = set()
    for index, item in enumerate(artifacts):
        if not isinstance(item, dict) or set(item) != {"role", "entryId", "file", "sha256"}:
            raise Refused(f"review packet artifacts[{index}] has an unknown shape")
        if item.get("role") != "entry-packet":
            raise Refused(f"review packet artifacts[{index}] has unknown role {item.get('role')!r}")
        entry = item.get("entryId")
        if not isinstance(entry, str) or not entry:
            raise Refused(f"review packet artifacts[{index}].entryId is not a non-empty string")
        name = safe_file(item.get("file"), f"artifacts[{index}].file")
        if name in seen_files or entry in seen_entries:
            raise Refused("review packet contains a duplicate entry-packet identity")
        seen_files.add(name)
        seen_entries.add(entry)
        expected = exact_digest(item.get("sha256"), f"artifacts[{index}].sha256")
        try:
            actual = digest((directory / name).read_bytes())
        except OSError as error:
            raise Refused(f"bound entry packet {name} cannot be read ({error})")
        if actual != expected:
            raise Refused(f"bound entry packet {name} hashes to {actual}, not manifest digest {expected}")


def reviewed_blob(sha, path):
    done = git("show", f"{sha}:{path}", check=False)
    if done.returncode != 0:
        detail = done.stderr.decode("utf-8", "replace").strip()
        raise Refused(f"reviewed commit {sha[:12]} does not contain bound source {path}: {detail}")
    return done.stdout


def ensure_commit(pr, sha):
    if git("cat-file", "-e", f"{sha}^{{commit}}", check=False).returncode == 0:
        return
    errors = []
    for spec in (f"pull/{pr}/head", sha):
        done = git("fetch", "--no-tags", "origin", spec, check=False)
        if done.returncode != 0:
            errors.append(done.stderr.decode("utf-8", "replace").strip())
        if git("cat-file", "-e", f"{sha}^{{commit}}", check=False).returncode == 0:
            return
    detail = "; ".join(e for e in errors if e) or "object absent after fetch"
    raise Refused(f"cannot obtain reviewed commit {sha}: {detail}")


def verify_sources(sha, sources, has_entries):
    if not isinstance(sources, list):
        raise Refused("review packet sources must be a list")
    allowed = {"provenance", "policy", "entry-packet-tool"}
    required = {"provenance": "provenance.json", "policy": POLICY}
    if has_entries:
        required["entry-packet-tool"] = "tools/entry-packet.py"

    seen_roles = {}
    seen_paths = set()
    for index, item in enumerate(sources):
        if not isinstance(item, dict) or set(item) != {"role", "path", "sha256"}:
            raise Refused(f"review packet sources[{index}] has an unknown shape")
        role = item.get("role")
        path = item.get("path")
        if role not in allowed:
            raise Refused(f"review packet sources[{index}] has unknown role {role!r}")
        if not isinstance(path, str) or not path or path.startswith("/") or ".." in pathlib.PurePosixPath(path).parts:
            raise Refused(f"review packet sources[{index}].path is not a repository-relative path")
        if role in seen_roles or path in seen_paths:
            raise Refused("review packet contains a duplicate review-source identity")
        seen_roles[role] = path
        seen_paths.add(path)
        expected = exact_digest(item.get("sha256"), f"sources[{index}].sha256")
        actual = digest(reviewed_blob(sha, path))
        if actual != expected:
            raise Refused(f"reviewed source {path} hashes to {actual}, not manifest digest {expected}")

    for role, path in required.items():
        if seen_roles.get(role) != path:
            raise Refused(f"review packet must bind reviewed source {role} at {path}")


def validate_manifest(pr, path, document, sha_override):
    allowed = {"formatVersion", "pullRequest", "reviewedCommit", "baseCommit", "packet",
               "map", "sources", "artifacts", "context"}
    if set(document) != allowed:
        extra = sorted(set(document) - allowed)
        missing = sorted(allowed - set(document))
        raise Refused(f"review packet manifest fields are not format {PACKET_FORMAT}; "
                      f"missing={missing}, unknown={extra}")

    packet_pr = document.get("pullRequest")
    if packet_pr != pr:
        raise Refused(f"review packet belongs to PR #{packet_pr}, not requested PR #{pr}")
    sha = exact_sha(document.get("reviewedCommit"), "reviewedCommit")
    exact_sha(document.get("baseCommit"), "baseCommit")
    if sha_override is not None and sha_override != sha:
        raise Refused(f"--sha {sha_override} disagrees with review packet commit {sha}")

    packet = document.get("packet")
    if not isinstance(packet, dict):
        raise Refused("review packet packet identity must be an object")
    verify_file(path.parent, packet, "packet")

    artifacts = document.get("artifacts")
    verify_artifacts(path.parent, artifacts)

    map_identity = document.get("map")
    if not isinstance(map_identity, dict) or set(map_identity) != {"packageId", "version", "nupkgSha256"}:
        raise Refused("review packet map identity has an unknown shape")
    if not isinstance(map_identity.get("packageId"), str) or not isinstance(map_identity.get("version"), str):
        raise Refused("review packet map packageId/version must be strings")
    nupkg = map_identity.get("nupkgSha256")
    if nupkg and not SHA256.fullmatch(nupkg):
        raise Refused("review packet map.nupkgSha256 is not a lowercase sha256 digest")

    context = document.get("context")
    if not isinstance(context, dict) or set(context) != {"pullRequestSha256", "issueSha256"}:
        raise Refused("review packet context identity has an unknown shape")
    exact_digest(context.get("pullRequestSha256"), "context.pullRequestSha256")
    exact_digest(context.get("issueSha256"), "context.issueSha256")

    ensure_commit(pr, sha)
    verify_sources(sha, document.get("sources"), bool(artifacts))
    return sha


def policy_at(sha):
    try:
        settings = json.loads(reviewed_blob(sha, POLICY).decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise Refused(f"{POLICY} at reviewed commit {sha[:12]} cannot be read ({error})")
    return settings


def context_for(reviewer, settings):
    review = settings.get("review") or {}
    if reviewer == SEMANTIC:
        context = review.get("semanticContext")
        if not context:
            raise Refused(f"reviewed {POLICY} sets no review.semanticContext")
        return context
    chain = review.get("independentFallback") or []
    for link in chain:
        if isinstance(link, dict) and link.get("id") == reviewer and link.get("context"):
            return link["context"]
    known = ", ".join([SEMANTIC] + [link.get("id", "?") for link in chain if isinstance(link, dict)])
    raise Refused(f"{reviewer!r} is not a reviewer the reviewed commit configures. Known: {known}. "
                  f"Adding one is an edit to {POLICY}, not to this script.")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="record-verdict.py", description=__doc__.split("\n")[0])
    parser.add_argument("--pr", type=int, required=True, help="the pull request reviewed")
    parser.add_argument("--packet", required=True,
                        help="the .review.json identity manifest emitted by review-packet.py")
    parser.add_argument("--reviewer", required=True,
                        help=f"'{SEMANTIC}', or an id from review.independentFallback in the reviewed policy")
    parser.add_argument("--verdict", required=True, choices=("pass", "fail"))
    parser.add_argument("--note", default="", help="one line, shown beside the status")
    parser.add_argument("--sha", help="legacy compatibility assertion; must equal packet reviewedCommit")
    parser.add_argument("--dry-run", action="store_true", help="print what would be recorded, and record nothing")
    args = parser.parse_args(argv)

    try:
        manifest, document = load_manifest(args.packet)
        sha = validate_manifest(args.pr, manifest, document, args.sha)
        settings = policy_at(sha)
        context = context_for(args.reviewer, settings)

        pull = json.loads(gh("pr", "view", str(args.pr), "--json", "number,headRefOid,state"))
        head = pull.get("headRefOid")
        if not head or not SHA40.fullmatch(head):
            raise Refused(f"PR #{args.pr} has no exact current head commit")
        if head != sha:
            print(f"note: packet reviewed {sha[:12]}, while PR #{args.pr} is now at {head[:12]}. "
                  "The verdict will be historical evidence on the reviewed commit and satisfies no current gate.",
                  file=sys.stderr)

        repository = json.loads(gh("repo", "view", "--json", "nameWithOwner"))["nameWithOwner"]
        state = "success" if args.verdict == "pass" else "failure"
        description = (args.note or f"{args.verdict} by {args.reviewer}")[:140]

        if args.dry_run:
            print(f"{repository} {sha} {context} {state} {description!r}")
            return 0
        gh("api", f"repos/{repository}/statuses/{sha}", "-X", "POST",
           "-f", f"state={state}", "-f", f"context={context}", "-f", f"description={description}")
    except Refused as error:
        print(f"record-verdict: REFUSED -- {error}", file=sys.stderr)
        return 1

    print(f"recorded {state} at {context} on reviewed commit {sha[:12]} (PR #{args.pr})")
    if head != sha:
        print("The pull request has moved; this verdict is retained only as evidence about the reviewed bytes.")
    if args.verdict == "fail":
        print("A FAIL remains evidence about these exact reviewed bytes. A changed head still requires fresh review; "
              "moving the branch never turns this failure into a pass on different bytes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
