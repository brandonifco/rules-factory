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

**Every verdict leaves an attestation** (rules-factory 0071). Beside the identity it consumed, the
recorder writes `<identity>.attestation.json`: what kind of review it was, the claims it covered and
the fingerprint of every unit each rests on, the findings, the parent it follows, what it retained
and what it invalidated, and why. Its SHA-256 goes into the status description, so an attestation
edited afterwards no longer matches what was recorded. Commit it under `reviews/attestations/` with
the repair that answers it: `tools/review-scope.py`'s `delta` reads it from there, and bounds the next
review by what the repair could have changed.

**Which context a verdict posts is the attestation's type.** A full or final PASS posts the context
the merge gate requires. A delta PASS posts `<context>/delta`, which nothing requires: a chain of
bounded reviews reaches the merge only through one final acceptance review. A FAIL of any kind
posts a failure, which blocks. And a carry -- a packet `review-scope.py`'s `delta` wrote because nothing
a comprehensive PASS rested on moved -- posts that PASS again at the new head, and nothing else.

**A failure says what failed.** A scoped FAIL names the claim each blocking finding is about
(`--finding CLAIM=TEXT`, or `--findings <file>`), because the review after the repair rereads
exactly those claims whether or not their bytes moved.

**What this cannot check.** Which person/model actually produced the verdict, or that the provider
chain was tried in order. The packet binding is an integrity boundary, not reviewer authentication.
Provider signatures or authentication are deliberately outside this mechanism.

Standard library only, plus `gh` (or `$RULES_ENGINE_GH`).
"""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys

# The attestation is built by the factory's own model, vendored under scripts/factory, and an
# import leaves bytecode beside it unless this is set first (#194).
sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parents[1]
POLICY = ".github/agent-policy.json"
PROVENANCE = "provenance.json"
SEMANTIC = "semantic"
PACKET_FORMAT = 2
#: The cuts that `tools/review-packet.py` makes with its `--role` flag, and the whole packet.
#: Which bytes a reviewer actually read now depends on the cut as well as on the commit, so the
#: identity names it and this recorder holds a verdict to what its cut could carry.
STRUCTURAL, INDEPENDENT, ALL = "structural", "independent", "all"
ROLES = (STRUCTURAL, SEMANTIC, INDEPENDENT, ALL)
#: Which cut can carry which verdict. A structural packet carries none: the steward's findings go
#: to the orchestrator, and this engine's policy configures no context to record one under.
CARRIES = {ALL: ("the semantic reviewer and the independent chain", (SEMANTIC, INDEPENDENT)),
           SEMANTIC: ("the semantic reviewer", (SEMANTIC,)),
           INDEPENDENT: ("the independent chain", (INDEPENDENT,)),
           STRUCTURAL: ("nobody", ())}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
#: What a packet identity may say it was for (0071). `carry` is written by `review-scope.py`'s `delta`
#: when nothing moved: no review, and a comprehensive PASS posted again.
REVIEW_TYPES = ("full", "delta", "final", "carry")
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
    """Parse the identity and verify every human-facing packet byte it binds."""
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
                      f"this recorder supports {PACKET_FORMAT}. A packet is ephemeral and is never "
                      f"committed, so an older one is regenerated rather than migrated: run "
                      f"`tools/review-packet.py` again and record from the packet that reviewer read.")
    role = document.get("reviewRole")
    if role not in ROLES:
        raise Refused(f"review packet identity has no valid reviewRole (got {role!r}); "
                      f"one of {', '.join(ROLES)}. Which bytes a reviewer was given depends on the cut, "
                      f"so a verdict cannot be bound to a packet that does not say which cut it is.")

    pull = document.get("pullRequest")
    if not isinstance(pull, int) or isinstance(pull, bool) or pull < 1:
        raise Refused("review packet identity has no valid pullRequest")
    reviewed = git_sha(document.get("reviewedCommit"), "reviewedCommit")
    base = git_sha(document.get("baseCommit"), "baseCommit")

    directory = identity_path.parent
    human_path, human_digest = packet_member(directory, document.get("reviewPacket"), "review packet")
    review_type = document.get("reviewType", "full")
    if review_type not in REVIEW_TYPES:
        raise Refused(f"reviewType {review_type!r} is not one of {', '.join(REVIEW_TYPES)}")
    scope = prior = None
    if document.get("scope") is not None:
        scope_path, _ = packet_member(directory, document.get("scope"), "review scope")
        try:
            scope = json.loads(scope_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise Refused(f"review scope cannot be read ({error})")
    if document.get("prior") is not None:
        prior_path, _ = packet_member(directory, document.get("prior"), "prior attestation")
        try:
            prior = json.loads(prior_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise Refused(f"prior attestation cannot be read ({error})")
        prior = prior if isinstance(prior, dict) else None
    if review_type in ("delta", "carry", "final") and (scope is None or prior is None):
        raise Refused(f"a {review_type} packet carries the scope and the prior attestation it follows, and this "
                      f"identity does not; regenerate it")

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
    mapped = context.get("maps")
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
    if not isinstance(mapped, list) or not mapped:
        raise Refused("reviewContext.maps is not a non-empty list of the map packages this engine "
                      "was produced from")
    for index, package in enumerate(mapped):
        if not isinstance(package, dict):
            raise Refused(f"reviewContext.maps[{index}] is not an object")
        for field in ("packageId", "version", "nupkgSha256"):
            if not isinstance(package.get(field), str):
                raise Refused(f"reviewContext.maps[{index}].{field} is not a string")

    # The entry packets are what a semantic reviewer is told to read before the diff, and they are
    # built from map bytes the packet either did or did not hold to the reviewed commit's declared
    # digest. Recording a verdict from a packet that says it did not is recording a judgement about
    # bytes nobody proved the commit carried, and the record cannot tell it from one that did
    # (#372). So the relationship is checked here too, rather than trusted to the producer.
    #
    # An engine composed of several map packages (rules-factory 0067) is checked package by
    # package. One unbound map among several is the whole failure, not a fraction of it: the
    # entry packets are built from the composition, so bytes nobody held to the record reach the
    # reviewer through it exactly as they would through a single map.
    if verified_entries:
        for index, package in enumerate(mapped):
            where = f"reviewContext.maps[{index}] ({package.get('packageId')})"
            read = package.get("readSha256")
            declared_map = package.get("declaredSha256")
            if read is None:
                raise Refused(f"this packet's entry evidence was never bound to the reviewed commit: "
                              f"{where}.readSha256 is null, so the map its {len(verified_entries)} "
                              f"entry packet(s) were built from was never checked against the digest "
                              f"{reviewed[:12]} declares. Regenerate the packet with --package-map and review "
                              f"those bytes; a verdict on unbound evidence is indistinguishable in the record "
                              f"from one on checked evidence, which is why it is refused.")
            sha256(read, f"{where}.readSha256")
            sha256(declared_map, f"{where}.declaredSha256")
            if read != declared_map:
                raise Refused(f"the map this packet's entry packets were read from ({read[:12]}) is not the map "
                              f"the reviewed commit declares ({declared_map[:12]}) for "
                              f"{package.get('packageId')}; the entry evidence is not "
                              f"{reviewed[:12]}'s own. Regenerate the packet from the declared map.")

    return {
        "path": identity_path,
        "role": role,
        "sha256": digest(raw),
        "pullRequest": pull,
        "reviewedCommit": reviewed,
        "baseCommit": base,
        "reviewPacket": human_path,
        "reviewPacketSha256": human_digest,
        "entryPackets": verified_entries,
        "policy": policy,
        "document": document,
        "reviewType": review_type,
        "scope": scope,
        "prior": prior,
    }


def role_carries(reviewer, role):
    """Refuse a verdict the packet's cut could not have been formed on.

    A `--role semantic` packet holds the entry packets and not the pull request's argument; a
    `--role structural` packet holds neither, because the steward is forbidden to judge the rule.
    Recording a semantic verdict from a structural packet would put a judgement about the map into
    the record having read none of it -- the unbound entry evidence #372 refuses, arriving through
    the role rather than through the digest. The record cannot tell the two apart afterwards, which
    is why this is refused here rather than left to the caller.
    """
    who, allowed = CARRIES[role]
    kind = SEMANTIC if reviewer == SEMANTIC else INDEPENDENT
    if kind not in allowed:
        # The command is built whole and interpolated as one span: a rail that spells a command
        # out is run exactly as written by a test, and half of one is not a command (#203).
        command = f"tools/review-packet.py <pr number> --role {kind}"
        raise Refused(f"this packet was cut for the {role} review, which carries a verdict from {who}. "
                      f"{reviewer!r} is {'the semantic reviewer' if kind == SEMANTIC else 'an independent reviewer'}, "
                      f"and the bytes that role needs are not in it. Generate the packet the reviewer "
                      f"actually read: `{command}`.")


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


def scope_model():
    sys.path.insert(0, str(ROOT / "scripts" / "factory"))
    try:
        import reviewscope
    except ImportError as error:
        raise Refused(f"scripts/factory/reviewscope.py is not importable ({error}); run `factory produce` again")
    return reviewscope


def findings_of(args, scope):
    """(blocking, non-blocking) as the caller gave them, each blocking one bound to a claim where it can be."""
    blocking, observations = [], []
    if args.findings:
        try:
            given = json.loads(pathlib.Path(args.findings).read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise Refused(f"--findings {args.findings} cannot be read ({error})")
        if not isinstance(given, dict):
            raise Refused("--findings is a JSON object with blocking and nonBlocking lists")
        blocking += [dict(f) for f in given.get("blocking") or [] if isinstance(f, dict)]
        observations += [dict(f) for f in given.get("nonBlocking") or [] if isinstance(f, dict)]
    for text in args.finding:
        claim, separator, summary = text.partition("=")
        if not separator or not summary.strip():
            raise Refused(f"--finding {text!r} is not CLAIM=TEXT")
        blocking.append({"claim": claim.strip(), "summary": summary.strip()})
    claims = sorted((scope or {}).get("state", {}).get("claims") or {})
    if args.verdict == "fail" and not blocking:
        blocking.append({"summary": args.note or f"fail by {args.reviewer}", **({"claim": claims[0]} if len(claims) == 1 else {})})
    if args.verdict == "pass" and blocking:
        raise Refused(f"a pass cannot carry {len(blocking)} blocking finding(s); a blocking finding is a fail")
    return blocking, observations


def attest(args, identity, model):
    """The attestation of this verdict, validated, and checked against the parent it follows."""
    scope = identity["scope"]
    blocking, observations = findings_of(args, scope)
    document = identity["document"]
    packet = {"identitySha256": identity["sha256"], "sha256": identity["reviewPacketSha256"],
              "role": identity["role"],
              "entryPackets": [{"entryId": e, "sha256": d} for e, _, d in identity["entryPackets"]]}
    telemetry = dict((scope or {}).get("telemetry") or {})
    if args.tokens is not None:
        telemetry["tokens"] = args.tokens
    common = dict(
        reviewed_commit=identity["reviewedCommit"], base_commit=identity["baseCommit"],
        review_type=identity["reviewType"], reviewer={"id": args.reviewer, "family": args.reviewer_family},
        packet=packet, result="PASS" if args.verdict == "pass" else "FAIL", blocking=blocking,
        non_blocking=observations, evidence_used=[{"kind": "entry-packet", "entryId": e, "sha256": d}
                                                 for e, _, d in identity["entryPackets"]],
        telemetry=telemetry,
        audit={"recordedAt": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    if scope is None:
        # A packet with no entry evidence -- or one written before 0071 -- leaves an attestation
        # that says so, and can never be the parent of a delta (`legacy-evidence-unscoped`).
        attestation = model.build_attestation(
            project={"engine": None}, charter={}, maps=[{"packageId": m.get("packageId"), "version": m.get("version")}
                                                          for m in document["reviewContext"].get("maps") or []],
            corpora=[], current={"units": {}, "claims": {}}, scoped=False, **common)
    else:
        attestation = model.build_attestation(
            project=scope.get("project") or {}, charter=scope.get("charter") or {}, maps=scope.get("maps") or [],
            corpora=scope.get("corpora") or [], current=scope["state"], parent=identity["prior"],
            impact_record=scope.get("impact") or {}, locators=scope.get("locators"), **common)
    problems = model.validate_attestation(attestation)
    if identity["prior"] is not None and identity["reviewType"] == "delta":
        problems += model.check_chain(attestation, identity["prior"])
    if problems:
        raise Refused("the attestation this verdict would leave is not well formed, so nothing is recorded:\n"
                      + "\n".join(f"  - {p}" for p in problems))
    return attestation


def carried(args, identity, model, context):
    """(context, description tail) for a carry: a comprehensive PASS posted again, and nothing else."""
    prior, impact = identity["prior"], (identity["scope"] or {}).get("impact") or {}
    if args.verdict != "pass" or args.reviewer != SEMANTIC:
        raise Refused("a carry records the semantic reviewer's earlier pass again, and nothing else: "
                      "--reviewer semantic --verdict pass")
    if not model.may_carry(prior, impact):
        raise Refused("nothing can be carried: the prior attestation is not a full or final PASS, or something it "
                      "rested on moved. Review the change.")
    return context, f"carried from {prior['reviewedCommit'][:12]}; attestation {model.attestation_digest(prior)}"


def main(argv=None):
    parser = argparse.ArgumentParser(prog="record-verdict.py", description=__doc__.split("\n")[0])
    parser.add_argument("--pr", type=int, required=True, help="the pull request reviewed")
    parser.add_argument("--packet", help="the .review.json identity emitted by tools/review-packet.py")
    parser.add_argument("--reviewer", required=True,
                        help=f"'{SEMANTIC}', or an id from the reviewed packet's independent review chain")
    parser.add_argument("--verdict", required=True, choices=("pass", "fail"))
    parser.add_argument("--note", default="", help="one line, shown beside the status")
    parser.add_argument("--finding", action="append", default=[], metavar="CLAIM=TEXT",
                        help="a blocking finding and the claim it is about (entry:<id>, invariant:<id>, "
                             "change:<path>); repeat for each")
    parser.add_argument("--findings", metavar="PATH",
                        help='a JSON file: {"blocking": [{"claim", "summary", "category"}], "nonBlocking": [...]}')
    parser.add_argument("--reviewer-family", default=None, help="the reviewer's model family, where known")
    parser.add_argument("--tokens", type=int, default=None,
                        help="the review's token count, only where the environment reports it reliably")
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
        role_carries(args.reviewer, identity["role"])
        model = scope_model()
        attestation = None
        if identity["reviewType"] == "carry":
            context, description_tail = carried(args, identity, model, context)
        else:
            attestation = attest(args, identity, model)
            context, _ = model.status_for(attestation, context)
            description_tail = f"attestation {model.attestation_digest(attestation)}"
        pull = json.loads(gh("pr", "view", str(args.pr), "--json", "number,headRefOid,state"))
        head = pull.get("headRefOid")
        if not head:
            raise Refused(f"PR #{args.pr} has no head commit")
        if head != reviewed:
            raise Refused(f"review packet covers {reviewed[:12]}, but PR #{args.pr} is now {head[:12]}; "
                          f"the earlier review cannot approve the newer head. Regenerate the packet and re-review.")

        state = "success" if args.verdict == "pass" else "failure"
        packet_tag = identity["sha256"][:12]
        # The digest is the part a later reader checks, so it is never the part cut to fit.
        tail = f"; packet {packet_tag}; {description_tail}"
        description = (args.note or f"{args.verdict} by {args.reviewer}")[:max(0, 140 - len(tail))] + tail
        repository = json.loads(gh("repo", "view", "--json", "nameWithOwner"))["nameWithOwner"]

        if args.dry_run:
            print(f"{repository} {reviewed} {context} {state} {description!r} packet={identity['path']}")
            return 0
        # Written before the status is posted: a file whose digest no status names is merely unusable,
        # and a status naming a digest nobody kept would be a verdict nobody can bound a review by.
        if attestation is not None:
            written = identity["path"].with_name(identity["path"].name.replace(".review.json", "") + ".attestation.json")
            written.write_bytes(model.pretty(attestation))
        gh("api", f"repos/{repository}/statuses/{reviewed}", "-X", "POST",
           "-f", f"state={state}", "-f", f"context={context}", "-f", f"description={description}")
    except Refused as error:
        print(f"record-verdict: REFUSED -- {error}", file=sys.stderr)
        return 1

    print(f"recorded {state} at {context} on {reviewed[:12]} (PR #{args.pr}, packet {packet_tag})")
    if attestation is not None:
        committed = f"{model.ATTESTATIONS}/pr-{args.pr}-{reviewed[:12]}-{attestation['reviewType']}.json"
        print(f"attestation {model.attestation_digest(attestation)} written to {written}")
        print(f"commit it as {committed}: the next review of this pull request reads it from there")
        if attestation["reviewType"] == "delta" and attestation["result"] == "PASS":
            print("A delta PASS does not satisfy the merge gate. The final acceptance review does: "
                  f"`tools/review-packet.py {args.pr} --role semantic --review final --prior {committed} "
                  f"--package-map <path>` once the attestation is committed.")
    if args.verdict == "fail":
        print("A recorded failure blocks the merge outright. It is answered by fixing the code, fixing the map, or "
              "getting an owner's ruling -- never by asking another provider until one agrees.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
