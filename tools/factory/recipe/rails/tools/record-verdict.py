#!/usr/bin/env python3
"""Record a review verdict only from the exact machine-bound packet that was reviewed.

    tools/record-verdict.py --pr 12 --packet /tmp/pr-12-abc.review.json \
        --reviewer semantic --verdict pass
    tools/record-verdict.py --pr 12 --packet /tmp/pr-12-abc.review.json \
        --reviewer <id from the chain> --verdict fail --note "row 7 is wrong"

Emitted by rules-factory as a managed file (decisions 0029 and 0049).

The format-1 review manifest is the evidence object. It identifies the reviewed commit, the human
packet, every generated entry packet and the reviewed tree's policy/provenance/tooling identities.
This command re-hashes those actual bytes before posting anything. It never chooses the reviewed
commit from the pull request's current head.

If the PR has advanced, the verdict may still be recorded on the reviewed commit as historical
evidence, but it satisfies no current gate. A PASS and a FAIL obey the same identity rule.

What this still cannot check is which model actually produced the verdict or whether the fallback
chain was tried in order. Those remain operator obligations under decision 0029.

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
PROVENANCE = "provenance.json"
ENTRY_PACKET = "tools/entry-packet.py"
SEMANTIC = "semantic"
FORMAT = 1
COMMIT = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")


class Refused(Exception):
    """Something that must not be recorded. Nothing is posted."""


def gh(*args, check=True):
    command = [os.environ.get("RULES_ENGINE_GH", "gh"), *args]
    done = subprocess.run(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        cwd=ROOT, timeout=120,
    )
    if check and done.returncode != 0:
        raise Refused(f"{' '.join(command)} failed: {done.stderr.strip() or done.stdout.strip()}")
    return done.stdout


def git_result(*args):
    return subprocess.run(
        ["git", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=ROOT, timeout=300,
    )


def git_text(*args):
    done = git_result(*args)
    if done.returncode != 0:
        raise Refused(
            f"git {' '.join(args)} failed: {done.stderr.decode('utf-8', errors='replace').strip()}"
        )
    return done.stdout.decode("utf-8")


def commit_exists(sha):
    if not COMMIT.fullmatch(sha or ""):
        return False
    done = git_result("cat-file", "-e", f"{sha}^{{commit}}")
    if done.returncode != 0:
        return False
    return git_text("rev-parse", "--verify", f"{sha}^{{commit}}").strip() == sha


def ensure_reviewed_commit(sha, pr, head_ref):
    if not COMMIT.fullmatch(sha or ""):
        raise Refused(f"packet reviewedCommit is not a full commit SHA: {sha!r}")
    if commit_exists(sha):
        return
    for ref in (f"pull/{pr}/head", head_ref):
        if not ref:
            continue
        subprocess.run(
            ["git", "fetch", "--no-tags", "origin", ref],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ROOT, timeout=300,
        )
        if commit_exists(sha):
            return
    raise Refused(
        f"packet reviewed commit {sha} is not available exactly; refusing rather than "
        "substituting the current checkout or PR head"
    )


def no_duplicate_keys(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise Refused(f"review packet manifest repeats JSON key {key!r}")
        out[key] = value
    return out


def read_manifest(path):
    try:
        text = path.read_text(encoding="utf-8")
        document = json.loads(text, object_pairs_hook=no_duplicate_keys)
    except Refused:
        raise
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise Refused(f"review packet manifest cannot be read ({path}: {error})")
    if not isinstance(document, dict):
        raise Refused("review packet manifest is not a JSON object")
    return document


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_path(path):
    try:
        return sha256_bytes(path.read_bytes())
    except OSError as error:
        raise Refused(f"cannot hash review artifact {path}: {error}")


def canonical_identity(document):
    payload = {key: value for key, value in document.items() if key != "identitySha256"}
    data = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return sha256_bytes(data)


def exact_keys(value, keys, what):
    if not isinstance(value, dict):
        raise Refused(f"{what} is not an object")
    expected = set(keys)
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise Refused(f"{what} has wrong fields (missing {missing}, extra {extra})")


def digest(value, what):
    if not isinstance(value, str) or not DIGEST.fullmatch(value):
        raise Refused(f"{what} is not a lowercase sha256 digest")
    return value


def companion(parent, name, what):
    if (
        not isinstance(name, str)
        or not name
        or name in (".", "..")
        or pathlib.Path(name).name != name
        or "/" in name
        or "\\" in name
    ):
        raise Refused(f"{what} filename must be one deterministic basename, got {name!r}")
    path = parent / name
    if not path.is_file():
        raise Refused(f"{what} is missing beside the manifest: {name}")
    return path


def validate_manifest(document, manifest_path, expected_pr):
    expected_top = {
        "reviewPacketFormat", "pullRequest", "reviewedCommit", "baseCommit",
        "packet", "artifacts", "entryPackets", "inputs", "identitySha256",
    }
    actual_top = set(document)
    if actual_top != expected_top:
        raise Refused(
            f"format-1 manifest has wrong fields (missing {sorted(expected_top - actual_top)}, "
            f"extra {sorted(actual_top - expected_top)})"
        )
    if document.get("reviewPacketFormat") != FORMAT:
        raise Refused(
            f"reviewPacketFormat {document.get('reviewPacketFormat')!r} is not supported; "
            f"this recorder requires format {FORMAT}"
        )
    if document.get("pullRequest") != expected_pr:
        raise Refused(
            f"packet is for PR #{document.get('pullRequest')}, not requested PR #{expected_pr}"
        )
    reviewed = document.get("reviewedCommit")
    base = document.get("baseCommit")
    if not COMMIT.fullmatch(reviewed or ""):
        raise Refused(f"reviewedCommit is not a full commit SHA: {reviewed!r}")
    if not COMMIT.fullmatch(base or ""):
        raise Refused(f"baseCommit is not a full commit SHA: {base!r}")

    claimed_identity = digest(document.get("identitySha256"), "identitySha256")
    actual_identity = canonical_identity(document)
    if claimed_identity != actual_identity:
        raise Refused(
            f"review manifest identity mismatch: says {claimed_identity}, recomputes to {actual_identity}"
        )

    packet = document.get("packet")
    exact_keys(packet, {"file", "sha256"}, "packet")
    packet_path = companion(manifest_path.parent, packet["file"], "human review packet")
    if sha256_path(packet_path) != digest(packet["sha256"], "packet.sha256"):
        raise Refused("human review packet sha256 does not match the manifest")

    artifacts = document.get("artifacts")
    if not isinstance(artifacts, list):
        raise Refused("artifacts is not a list")
    required = {
        "policy": POLICY,
        "provenance": PROVENANCE,
        "entry-packet-tool": ENTRY_PACKET,
    }
    seen_roles = set()
    seen_paths = set()
    for item in artifacts:
        exact_keys(item, {"role", "path", "sha256"}, "artifact")
        role, path = item["role"], item["path"]
        if role not in required:
            raise Refused(f"format-1 manifest has unknown artifact role {role!r}")
        if path != required[role]:
            raise Refused(f"artifact role {role!r} must bind {required[role]!r}, got {path!r}")
        if role in seen_roles or path in seen_paths:
            raise Refused(f"duplicate review artifact identity for {role!r}/{path!r}")
        seen_roles.add(role)
        seen_paths.add(path)
        digest(item["sha256"], f"artifact {role}.sha256")
    if seen_roles != set(required):
        raise Refused(f"format-1 manifest must bind exactly {sorted(required)}, got {sorted(seen_roles)}")

    entries = document.get("entryPackets")
    if not isinstance(entries, list):
        raise Refused("entryPackets is not a list")
    entry_ids = set()
    entry_files = set()
    for item in entries:
        exact_keys(item, {"entryId", "file", "sha256"}, "entry packet")
        entry_id = item["entryId"]
        if not isinstance(entry_id, str) or not entry_id:
            raise Refused("entry packet has no entryId")
        if entry_id in entry_ids:
            raise Refused(f"duplicate entry packet identity for {entry_id!r}")
        entry_ids.add(entry_id)
        entry_path = companion(manifest_path.parent, item["file"], f"entry packet {entry_id}")
        if item["file"] in entry_files:
            raise Refused(f"two entry packet identities name {item['file']!r}")
        entry_files.add(item["file"])
        if sha256_path(entry_path) != digest(item["sha256"], f"entry packet {entry_id}.sha256"):
            raise Refused(f"entry packet {entry_id} sha256 does not match the manifest")

    inputs = document.get("inputs")
    if not isinstance(inputs, list):
        raise Refused("inputs is not a list")
    if entries:
        if len(inputs) != 1:
            raise Refused("a packet with entry packets must bind exactly one package-map input")
        item = inputs[0]
        exact_keys(
            item,
            {"role", "file", "sha256", "packageId", "packageVersion", "mapPackageSha256"},
            "package-map input",
        )
        if item["role"] != "package-map":
            raise Refused(f"format-1 input role must be 'package-map', got {item['role']!r}")
        input_path = companion(manifest_path.parent, item["file"], "package-map input")
        if sha256_path(input_path) != digest(item["sha256"], "package-map input sha256"):
            raise Refused("package-map input sha256 does not match the manifest")
        for field in ("packageId", "packageVersion", "mapPackageSha256"):
            if not isinstance(item[field], str):
                raise Refused(f"package-map input {field} is not a string")
    elif inputs:
        raise Refused("a packet with no entry packets must not invent a package-map input")

    return reviewed, artifacts


def git_blob(commit, path):
    done = git_result("show", f"{commit}:{path}")
    if done.returncode != 0:
        raise Refused(
            f"reviewed commit {commit[:12]} has no readable {path}: "
            f"{done.stderr.decode('utf-8', errors='replace').strip()}"
        )
    return done.stdout


def verify_repository_artifacts(reviewed, artifacts):
    for item in artifacts:
        actual = sha256_bytes(git_blob(reviewed, item["path"]))
        if actual != item["sha256"]:
            raise Refused(
                f"reviewed {item['role']} digest mismatch at {reviewed[:12]}: "
                f"manifest says {item['sha256']}, Git tree is {actual}"
            )


def reviewed_policy(reviewed):
    try:
        document = json.loads(git_blob(reviewed, POLICY).decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise Refused(f"{POLICY} at reviewed commit cannot be read ({error})")
    if not isinstance(document, dict):
        raise Refused(f"{POLICY} at reviewed commit is not a JSON object")
    return document


def context_for(reviewer, settings):
    """The status context this reviewer records under, from the reviewed commit's policy."""
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
    known = ", ".join(
        [SEMANTIC]
        + [link.get("id", "?") for link in chain if isinstance(link, dict)]
    )
    raise Refused(
        f"{reviewer!r} is not a reviewer the reviewed commit configures. Known: {known}. "
        f"Adding one is an edit to {POLICY}, not to this script."
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="record-verdict.py", description=__doc__.split("\n")[0]
    )
    parser.add_argument("--pr", type=int, required=True, help="the pull request reviewed")
    parser.add_argument(
        "--packet", required=True,
        help="format-1 review packet manifest emitted by tools/review-packet.py",
    )
    parser.add_argument(
        "--reviewer", required=True,
        help=f"'{SEMANTIC}', or an id from review.independentFallback in the reviewed policy",
    )
    parser.add_argument("--verdict", required=True, choices=("pass", "fail"))
    parser.add_argument("--note", default="", help="one line, shown beside the status")
    parser.add_argument(
        "--sha",
        help="legacy compatibility assertion only; if supplied it must equal packet reviewedCommit",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="verify the complete packet identity and print what would be recorded",
    )
    args = parser.parse_args(argv)

    try:
        manifest_path = pathlib.Path(args.packet).expanduser().resolve()
        document = read_manifest(manifest_path)
        reviewed, artifacts = validate_manifest(document, manifest_path, args.pr)

        pull = json.loads(gh(
            "pr", "view", str(args.pr), "--json", "number,headRefOid,headRefName,state"
        ))
        head = pull.get("headRefOid") or ""
        if not COMMIT.fullmatch(head):
            raise Refused(f"PR #{args.pr} has no full head commit")
        ensure_reviewed_commit(reviewed, args.pr, pull.get("headRefName"))
        verify_repository_artifacts(reviewed, artifacts)

        if args.sha and args.sha != reviewed:
            raise Refused(
                f"--sha {args.sha} disagrees with packet reviewedCommit {reviewed}; "
                "the packet identity wins and disagreement is never an override"
            )

        settings = reviewed_policy(reviewed)
        context = context_for(args.reviewer, settings)
        state = "success" if args.verdict == "pass" else "failure"
        description = (args.note or f"{args.verdict} by {args.reviewer}")[:140]
        repository = json.loads(gh("repo", "view", "--json", "nameWithOwner"))["nameWithOwner"]

        if reviewed != head:
            print(
                f"note: packet reviewed {reviewed[:12]}, which is not current head {head[:12]}. "
                "The verdict will be recorded only on the reviewed commit and satisfies no current gate.",
                file=sys.stderr,
            )

        if args.dry_run:
            print(f"{repository} {reviewed} {context} {state} {description!r}")
            return 0

        gh(
            "api", f"repos/{repository}/statuses/{reviewed}", "-X", "POST",
            "-f", f"state={state}", "-f", f"context={context}",
            "-f", f"description={description}",
        )
    except Refused as error:
        print(f"record-verdict: REFUSED -- {error}", file=sys.stderr)
        return 1

    print(f"recorded {state} at {context} on {reviewed[:12]} (PR #{args.pr})")
    if reviewed != head:
        print(
            f"PR #{args.pr} is now {head[:12]}; this historical verdict does not satisfy its gate."
        )
    if args.verdict == "fail":
        print(
            "A recorded failure is evidence about the reviewed bytes. The current head still needs "
            "its own required review; a fallback provider is never used merely to disagree."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
