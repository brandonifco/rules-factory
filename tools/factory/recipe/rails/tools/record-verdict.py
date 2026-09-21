#!/usr/bin/env python3
"""Record a review verdict from the exact packet identity the reviewer read.

    tools/record-verdict.py --pr 12 --packet /tmp/.../pr-12-abcdef123456.review.json \
        --reviewer semantic --verdict pass
    tools/record-verdict.py --pr 12 --packet /tmp/.../pr-12-abcdef123456.review.json \
        --reviewer <id from the packet's review chain> --verdict fail --note "row 7 is wrong"

Emitted by rules-factory as a managed file (decision 0029).

**Why a packet identity and not the pull request's current head.** A verdict is evidence about the
bytes a reviewer actually read. The human review packet and its entry packets are produced from one
immutable reviewed commit, and the adjacent `.review.json` names that commit and hashes those exact
packet bytes. This recorder consumes that identity. It never turns "whatever the PR head is now"
into the thing that was reviewed.

If the pull request moved after the packet was made, recording is refused. Regenerate the packet
and review the new bytes. A stale review is useful history, but it is not approval of the new head.

**Why the entry evidence has to be bound.** The entry packets are the one input a semantic reviewer
is told to read before the diff, and they are built from a map the packet either held to the digest
the reviewed commit declares or did not. A packet that says it did not -- `readSha256: null` -- is
refused here rather than recorded, because a passing status formed on unproven entry bytes is
indistinguishable in the record from one formed on checked evidence (#372). Regenerate the packet
with `--package-map`.

**Why a commit status and not a comment.** A reviewer saying "pass" in a chat window is worth
nothing to the repository: the conversation ends, and what is left is a merged commit nobody can
tell was reviewed. A verdict here is a commit status on the packet's exact reviewed SHA, so the
merge gate can require it and a later commit cannot inherit it.

**The reviewer names itself.** `--reviewer semantic` records under the semantic context captured
from the reviewed commit's policy in the packet identity. Any other id must be one of that same
captured independent chain. The caller's current checkout cannot silently substitute a newer
policy for the one the reviewer saw.

**A fail is a fail.** `tools/conformance-gate.py` treats a recorded failure at any configured
context as blocking, and a later pass at a different context does not clear it. The chain advances
when a provider is unavailable -- unreachable, rate-limited, returning no verdict at all -- never
because its verdict was unwelcome. A failure is answered by fixing the code, fixing the map, or
getting an owner's ruling.

**What this cannot check.** Which person/model actually produced the verdict, or that the provider
chain was tried in order. The packet binding is an integrity boundary, not reviewer authentication.
Provider signatures or authentication are deliberately outside this mechanism.

Standard library only, plus `gh` (or `$RULES_ENGINE_GH`).
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
SEMANTIC = "semantic"
PACKET_FORMAT = 1
SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")


class Refused(Exception):
    """Something that must not be recorded. Nothing is posted."""


def gh(*args, check=True):
    command = [os.environ.get("RULES_ENGINE_GH", "gh"), *args]
    done = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=ROOT, timeout=120)
    if check and done.returncode != 0:
        raise Refused(f"{' '.join(command)} failed: {done.stderr.strip() or done.stdout.strip()}")
    return done.stdout


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha256(value, what):
    if not isinstance(value, str) or not SHA256.fullmatch(value):
        raise Refused(f"{what} is not a lowercase SHA-256 digest")
    return value


def git_sha(value, what):
    if not isinstance(value, str) or not GIT_SHA.fullmatch(value):
        raise Refused(f"{what} is not a full lowercase 40-character commit SHA")
    return value


def packet_member(directory, record, what):
    """Read and verify one packet-local file named by the identity."""
    if not isinstance(record, dict):
        raise Refused(f"{what} identity is not an object")
    name = record.get("path")
    if not isinstance(name, str) or not name or pathlib.PurePath(name).name != name:
        raise Refused(f"{what} path must be one packet-local file name, not {name!r}")
    expected = sha256(record.get("sha256"), f"{what} sha256")
    path = directory / name
    try:
        data = path.read_bytes()
    except OSError as error:
        raise Refused(f"{what} is missing or unreadable ({path}: {error})")
    actual = digest(data)
    if actual != expected:
        raise Refused(f"{what} digest does not match {name}: packet says {expected}, bytes are {actual}")
    return path, actual


def packet_identity(path):
    """Parse format 1 and verify every human-facing packet byte it binds."""
    identity_path = pathlib.Path(path).expanduser().resolve()
    try:
        raw = identity_path.read_bytes()
        document = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise Refused(f"review packet identity cannot be read ({identity_path}: {error})")
    if not isinstance(document, dict):
        raise Refused("review packet identity is not a JSON object")
    if document.get("reviewPacketFormat") != PACKET_FORMAT:
        raise Refused(f"unsupported reviewPacketFormat {document.get('reviewPacketFormat')!r}; "
                      f"this recorder supports {PACKET_FORMAT}")

    pull = document.get("pullRequest")
    if not isinstance(pull, int) or isinstance(pull, bool) or pull < 1:
        raise Refused("review packet identity has no valid pullRequest")
    reviewed = git_sha(document.get("reviewedCommit"), "reviewedCommit")
    base = git_sha(document.get("baseCommit"), "baseCommit")

    directory = identity_path.parent
    human_path, human_digest = packet_member(directory, document.get("reviewPacket"), "review packet")

    entries = document.get("entryPackets")
    if not isinstance(entries, list):
        raise Refused("entryPackets is not a list")
    seen_entries = set()
    verified_entries = []
    for index, record in enumerate(entries):
        if not isinstance(record, dict):
            raise Refused(f"entryPackets[{index}] is not an object")
        entry_id = record.get("entryId")
        if not isinstance(entry_id, str) or not entry_id:
            raise Refused(f"entryPackets[{index}] has no entryId")
        if entry_id in seen_entries:
            raise Refused(f"entryPackets repeats {entry_id!r}")
        seen_entries.add(entry_id)
        entry_path, entry_digest = packet_member(directory, record, f"entry packet {entry_id!r}")
        verified_entries.append((entry_id, entry_path, entry_digest))

    context = document.get("reviewContext")
    if not isinstance(context, dict):
        raise Refused("reviewContext is not an object")
    policy = context.get("policy")
    provenance = context.get("provenance")
    mapped = context.get("map")
    if not isinstance(policy, dict) or policy.get("path") != POLICY:
        raise Refused(f"reviewContext.policy must identify {POLICY}")
    sha256(policy.get("sha256"), "reviewContext.policy sha256")
    semantic = policy.get("semanticContext")
    if not isinstance(semantic, str) or not semantic:
        raise Refused("reviewContext.policy has no semanticContext")
    chain = policy.get("independentFallback")
    if not isinstance(chain, list):
        raise Refused("reviewContext.policy.independentFallback is not a list")
    seen_reviewers = set()
    for index, link in enumerate(chain):
        if not isinstance(link, dict):
            raise Refused(f"reviewContext.policy.independentFallback[{index}] is not an object")
        reviewer = link.get("id")
        context_name = link.get("context")
        if not isinstance(reviewer, str) or not reviewer or not isinstance(context_name, str) or not context_name:
            raise Refused(f"reviewContext.policy.independentFallback[{index}] has no id/context")
        if reviewer in seen_reviewers:
            raise Refused(f"reviewContext.policy.independentFallback repeats reviewer {reviewer!r}")
        seen_reviewers.add(reviewer)

    if not isinstance(provenance, dict) or provenance.get("path") != PROVENANCE:
        raise Refused(f"reviewContext.provenance must identify {PROVENANCE}")
    sha256(provenance.get("sha256"), "reviewContext.provenance sha256")
    if not isinstance(mapped, dict):
        raise Refused("reviewContext.map is not an object")
    for field in ("packageId", "version", "nupkgSha256"):
        if not isinstance(mapped.get(field), str):
            raise Refused(f"reviewContext.map.{field} is not a string")

    # The entry packets are what a semantic reviewer is told to read before the diff, and they are
    # built from map bytes the packet either did or did not hold to the reviewed commit's declared
    # digest. Recording a verdict from a packet that says it did not is recording a judgement about
    # bytes nobody proved the commit carried, and the record cannot tell it from one that did
    # (#372). So the relationship is checked here too, rather than trusted to the producer.
    if verified_entries:
        read = mapped.get("readSha256")
        declared_map = mapped.get("declaredSha256")
        if read is None:
            raise Refused(f"this packet's entry evidence was never bound to the reviewed commit: "
                          f"reviewContext.map.readSha256 is null, so the map its {len(verified_entries)} "
                          f"entry packet(s) were built from was never checked against the digest "
                          f"{reviewed[:12]} declares. Regenerate the packet with --package-map and review "
                          f"those bytes; a verdict on unbound evidence is indistinguishable in the record "
                          f"from one on checked evidence, which is why it is refused.")
        sha256(read, "reviewContext.map.readSha256")
        sha256(declared_map, "reviewContext.map.declaredSha256")
        if read != declared_map:
            raise Refused(f"the map this packet's entry packets were read from ({read[:12]}) is not the map "
                          f"the reviewed commit declares ({declared_map[:12]}); the entry evidence is not "
                          f"{reviewed[:12]}'s own. Regenerate the packet from the declared map.")

    return {
        "path": identity_path,
        "sha256": digest(raw),
        "pullRequest": pull,
        "reviewedCommit": reviewed,
        "baseCommit": base,
        "reviewPacket": human_path,
        "reviewPacketSha256": human_digest,
        "entryPackets": verified_entries,
        "policy": policy,
        "document": document,
    }


def context_for(reviewer, packet_policy):
    """The status context this reviewer records under, from the reviewed packet's policy."""
    if reviewer == SEMANTIC:
        return packet_policy["semanticContext"]
    for link in packet_policy["independentFallback"]:
        if link["id"] == reviewer:
            return link["context"]
    known = ", ".join([SEMANTIC] + [link["id"] for link in packet_policy["independentFallback"]])
    raise Refused(f"{reviewer!r} is not a reviewer configured by the reviewed packet. Known: {known}. "
                  f"If the policy changed, regenerate and re-review the packet; do not reinterpret an old review.")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="record-verdict.py", description=__doc__.split("\n")[0])
    parser.add_argument("--pr", type=int, required=True, help="the pull request reviewed")
    parser.add_argument("--packet", help="the .review.json identity emitted by tools/review-packet.py")
    parser.add_argument("--reviewer", required=True,
                        help=f"'{SEMANTIC}', or an id from the reviewed packet's independent review chain")
    parser.add_argument("--verdict", required=True, choices=("pass", "fail"))
    parser.add_argument("--note", default="", help="one line, shown beside the status")
    parser.add_argument("--sha",
                        help="optional assertion of the reviewed SHA; it must equal the packet and never selects a SHA")
    parser.add_argument("--dry-run", action="store_true", help="print what would be recorded, and record nothing")
    args = parser.parse_args(argv)

    try:
        if not args.packet:
            raise Refused("a review packet identity is required. Generate one with "
                          "`tools/review-packet.py <pr>` and pass its .review.json path with --packet. "
                          "Legacy verdict statuses remain readable, but a new verdict is never inferred from the "
                          "pull request's current head.")
        identity = packet_identity(args.packet)
        if identity["pullRequest"] != args.pr:
            raise Refused(f"packet is for PR #{identity['pullRequest']}, not PR #{args.pr}")
        reviewed = identity["reviewedCommit"]
        if args.sha and args.sha != reviewed:
            raise Refused(f"--sha says {args.sha}, but the reviewed packet says {reviewed}")

        context = context_for(args.reviewer, identity["policy"])
        pull = json.loads(gh("pr", "view", str(args.pr), "--json", "number,headRefOid,state"))
        head = pull.get("headRefOid")
        if not head:
            raise Refused(f"PR #{args.pr} has no head commit")
        if head != reviewed:
            raise Refused(f"review packet covers {reviewed[:12]}, but PR #{args.pr} is now {head[:12]}; "
                          f"the earlier review cannot approve the newer head. Regenerate the packet and re-review.")

        state = "success" if args.verdict == "pass" else "failure"
        packet_tag = identity["sha256"][:12]
        description = (args.note or f"{args.verdict} by {args.reviewer}")
        description = f"{description}; packet {packet_tag}"[:140]
        repository = json.loads(gh("repo", "view", "--json", "nameWithOwner"))["nameWithOwner"]

        if args.dry_run:
            print(f"{repository} {reviewed} {context} {state} {description!r} packet={identity['path']}")
            return 0
        gh("api", f"repos/{repository}/statuses/{reviewed}", "-X", "POST",
           "-f", f"state={state}", "-f", f"context={context}", "-f", f"description={description}")
    except Refused as error:
        print(f"record-verdict: REFUSED -- {error}", file=sys.stderr)
        return 1

    print(f"recorded {state} at {context} on {reviewed[:12]} (PR #{args.pr}, packet {packet_tag})")
    if args.verdict == "fail":
        print("A recorded failure blocks the merge outright. It is answered by fixing the code, fixing the map, or "
              "getting an owner's ruling -- never by asking another provider until one agrees.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
