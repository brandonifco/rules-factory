#!/usr/bin/env python3
"""Record a review verdict against the exact commit it was formed on.

    tools/record-verdict.py --pr 12 --reviewer semantic --verdict pass --packet <pr-12-<sha>.review.json>
    tools/record-verdict.py --pr 12 --reviewer <id from the chain> --verdict fail --sha <sha> --note "row 7 is wrong"

Emitted by rules-factory as a managed file (decision 0029).

**Why a commit status and not a comment.** A reviewer saying "pass" in a chat window is worth
nothing to the repository: the conversation ends, and what is left is a merged commit nobody can
tell was reviewed. A verdict here is a commit status on the pull request's **head SHA**, which
makes two things true at once -- the merge gate can require it, and a further commit invalidates
it automatically, because the status is on the commit that was actually read. Re-reviewing a
changed pull request is then not a discipline anybody has to remember.

**The commit is named, never inherited (#334).** `--sha` used to default to the pull request's
current head. A reviewer who read commit A, and then ran the documented command after the branch
advanced to B, recorded a success on B -- a commit nobody had read -- and nothing in the output
said so. So an identity is now required: `--packet`, which takes it from the manifest
`tools/review-packet.py` wrote beside the packet that was actually read, or `--sha`, which is a
person stating what they reviewed. A `--packet` whose commit the pull request has since left is
refused outright: the artifact moved under the review, and that is exactly the case a verdict
must not survive. `--sha` still allows recording against an older commit for the record, and says
plainly that it satisfies no gate.

**The reviewer names itself.** `--reviewer semantic` records under the policy's semantic context;
any other id must be one of the configured independent chain, and records under that link's own
context. The chain is not collapsed into one generic context on purpose: a reader of a merged
commit must be able to tell a genuinely independent verdict from a same-family fallback without
opening a transcript.

**A fail is a fail.** `tools/conformance-gate.py` treats a recorded failure at any configured
context as blocking, and a later pass at a different context does not clear it. The chain advances
when a provider is unavailable -- unreachable, rate-limited, returning no verdict at all -- never
because its verdict was unwelcome. A failure is answered by fixing the code, fixing the map, or
getting an owner's ruling.

**What this cannot check.** Which model actually produced the verdict, or that the chain was tried
in order. Those remain obligations on whoever runs this, stated here rather than implied to be
enforced.

Standard library only, plus `gh` (or `$RULES_ENGINE_GH`).
"""
import argparse
import hashlib
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
POLICY = ".github/agent-policy.json"
SEMANTIC = "semantic"
# The manifest shape `tools/review-packet.py` writes. A newer one is refused rather than guessed at.
MANIFEST_VERSION = 1


class Refused(Exception):
    """Something that must not be recorded. Nothing is posted."""


def gh(*args, check=True):
    command = [os.environ.get("RULES_ENGINE_GH", "gh"), *args]
    done = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=ROOT, timeout=120)
    if check and done.returncode != 0:
        raise Refused(f"{' '.join(command)} failed: {done.stderr.strip() or done.stdout.strip()}")
    return done.stdout


def policy():
    try:
        with open(ROOT / POLICY, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError) as error:
        raise Refused(f"{POLICY} cannot be read ({error}); it is where the review contexts live")


def context_for(reviewer, settings):
    """The status context this reviewer records under, or a refusal naming the ones that exist."""
    review = settings.get("review") or {}
    if reviewer == SEMANTIC:
        context = review.get("semanticContext")
        if not context:
            raise Refused(f"{POLICY} sets no review.semanticContext")
        return context
    chain = review.get("independentFallback") or []
    for link in chain:
        if link.get("id") == reviewer:
            return link["context"]
    known = ", ".join([SEMANTIC] + [link.get("id", "?") for link in chain])
    raise Refused(f"{reviewer!r} is not a reviewer this engine configures. Known: {known}. "
                  f"Adding one is an edit to {POLICY}, not to this script.")


def reviewed(path, number):
    """The commit a packet manifest says was reviewed, with the packet's own bytes checked.

    The manifest names the packet's sha256. Checking it is what stops a verdict being recorded
    from a manifest whose packet has been edited, or paired with a different one.
    """
    try:
        with open(path, encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, ValueError) as error:
        raise Refused(f"{path} cannot be read as a packet manifest ({error}); "
                      f"tools/review-packet.py writes one beside every packet")
    version = manifest.get("manifestVersion")
    if version != MANIFEST_VERSION:
        raise Refused(f"{path} is manifest version {version!r}; this engine's record-verdict.py knows "
                      f"version {MANIFEST_VERSION}. Re-assemble the packet with this engine's "
                      f"tools/review-packet.py.")
    if manifest.get("pullRequest") != number:
        raise Refused(f"{path} is the packet for PR #{manifest.get('pullRequest')}, and this is "
                      f"--pr {number}")
    sha = manifest.get("reviewedSha")
    if not isinstance(sha, str) or not sha:
        raise Refused(f"{path} names no reviewedSha")
    packet_path, recorded = manifest.get("packetPath"), manifest.get("packetSha256")
    if not packet_path or not recorded:
        raise Refused(f"{path} does not name the packet it is about; a manifest without one "
                      f"identifies nothing")
    try:
        with open(packet_path, "rb") as handle:
            actual = hashlib.sha256(handle.read()).hexdigest()
    except OSError as error:
        raise Refused(f"the packet {packet_path} cannot be read ({error}); a verdict is recorded "
                      f"from a packet that still exists")
    if actual != recorded:
        raise Refused(f"{packet_path} has changed since the manifest was written: sha256 {actual[:12]} "
                      f"where the manifest says {recorded[:12]}. Re-assemble the packet and review it "
                      f"again rather than recording a verdict on bytes nobody read.")
    return sha


def main(argv=None):
    parser = argparse.ArgumentParser(prog="record-verdict.py", description=__doc__.split("\n")[0])
    parser.add_argument("--pr", type=int, required=True, help="the pull request reviewed")
    parser.add_argument("--reviewer", required=True,
                        help=f"'{SEMANTIC}', or an id from review.independentFallback in {POLICY}")
    parser.add_argument("--verdict", required=True, choices=("pass", "fail"))
    parser.add_argument("--note", default="", help="one line, shown beside the status")
    parser.add_argument("--sha", help="the commit reviewed, stated by the reviewer. One of --sha or "
                                      "--packet is required: a verdict never takes its commit from the "
                                      "pull request's current head (#334).")
    parser.add_argument("--packet", help="the .review.json manifest tools/review-packet.py wrote beside the "
                                         "packet that was read. The commit and the packet's digest come "
                                         "from it.")
    parser.add_argument("--dry-run", action="store_true", help="print what would be recorded, and record nothing")
    args = parser.parse_args(argv)

    try:
        settings = policy()
        context = context_for(args.reviewer, settings)
        if args.sha and args.packet:
            raise Refused("--sha and --packet both name the commit reviewed; pass one")
        if not args.sha and not args.packet:
            raise Refused("nothing names the commit reviewed. Pass --packet <the .review.json beside the "
                          "packet you read>, or --sha <the commit you read>. This used to default to the "
                          "pull request's current head, which recorded verdicts on commits nobody had "
                          "read (#334).")
        pull = json.loads(gh("pr", "view", str(args.pr), "--json", "number,headRefOid,state"))
        head = pull.get("headRefOid")
        if not head:
            raise Refused(f"PR #{args.pr} has no head commit")
        sha = reviewed(args.packet, args.pr) if args.packet else args.sha
        if args.packet and sha != head:
            # Fails closed. The packet is the reviewer's evidence about one commit, and the pull
            # request is no longer at it: neither commit can honestly take this verdict.
            raise Refused(f"the packet was assembled from {sha[:12]} and PR #{args.pr} is now at "
                          f"{head[:12]}. The pull request moved under the review. Re-assemble the packet "
                          f"at {head[:12]}, read it, and record that; or, to record the verdict you formed "
                          f"on {sha[:12]} for the record only, pass --sha {sha}.")
        if sha != head:
            # Deliberate, and worth saying out loud: a verdict on an older commit satisfies no gate,
            # because the gate asks about the head. Recording one is allowed for the record; it is
            # never a way to pass a pull request that has moved.
            print(f"note: recording against {sha[:12]}, which is not the head ({head[:12]}). This satisfies no "
                  f"gate: the gate asks about the head commit.", file=sys.stderr)
        state = "success" if args.verdict == "pass" else "failure"
        description = (args.note or f"{args.verdict} by {args.reviewer}")[:140]
        repository = json.loads(gh("repo", "view", "--json", "nameWithOwner"))["nameWithOwner"]

        if args.dry_run:
            print(f"{repository} {sha} {context} {state} {description!r}")
            return 0
        gh("api", f"repos/{repository}/statuses/{sha}", "-X", "POST",
           "-f", f"state={state}", "-f", f"context={context}", "-f", f"description={description}")
    except Refused as error:
        print(f"record-verdict: REFUSED -- {error}", file=sys.stderr)
        return 1
    print(f"recorded {state} at {context} on {sha[:12]} (PR #{args.pr})")
    if args.verdict == "fail":
        print("A recorded failure blocks the merge outright. It is answered by fixing the code, fixing the map, or "
              "getting an owner's ruling -- never by asking another provider until one agrees.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
