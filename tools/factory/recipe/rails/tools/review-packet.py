#!/usr/bin/env python3
"""Everything a reviewer needs about one pull request, assembled from one immutable commit.

    tools/review-packet.py <pr-number> [--out DIR] [--stdout] [--base REF]

Emitted by rules-factory as a managed file (decisions 0029 and 0049). `AGENTS.md` is the
contract, and `docs/agent-team.md` says which reviewer reads what.

The pull request's head SHA is read once. Repository evidence is then assembled from a private
detached worktree pinned to that exact SHA; the caller's branch, index and dirty files are never
inputs. Beside the Markdown packet, the command writes a deterministic format-1 JSON manifest that
binds the reviewed commit, resolved base, human packet, provenance, policy, entry-packet tool,
every generated entry packet and the exact package-map bytes those entry packets consumed.

A reviewer reads the entry packet before the implementation diff. The manifest is the machine
handoff to `tools/record-verdict.py`; Markdown prose is never parsed to decide what was reviewed.

Ephemeral: the packet bundle is written outside the repository and never committed.

Standard library only, plus `gh` (or `$RULES_ENGINE_GH`) and `git`.
"""
import argparse
import contextlib
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
POLICY = ".github/agent-policy.json"
OVERLAY = "overlay"
PROVENANCE = "provenance.json"
ENTRY_PACKET = "tools/entry-packet.py"
PACKET_ROOT_VARIABLE = "RULES_ENGINE_PACKET_ROOT"
ENTRY_MARKER = "<!-- rules-factory-entry:"
DIFF_LINE_BUDGET = 2000
SHA256 = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")


class Refused(Exception):
    """Something the packet cannot honestly assemble. Nothing is certified."""


def gh(*args):
    command = [os.environ.get("RULES_ENGINE_GH", "gh"), *args]
    try:
        done = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            cwd=ROOT, timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise Refused(
            f"cannot run {command[0]} ({error}); it is how a packet reads the issue and the PR"
        )
    if done.returncode != 0:
        raise Refused(f"{' '.join(command)} failed: {done.stderr.strip() or done.stdout.strip()}")
    return done.stdout


def git_result(*args, cwd=ROOT):
    try:
        return subprocess.run(
            ["git", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            cwd=cwd, timeout=300,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise Refused(f"cannot run git {' '.join(args)} ({error})")


def git(*args, cwd=ROOT):
    done = git_result(*args, cwd=cwd)
    if done.returncode != 0:
        raise Refused(f"git {' '.join(args)} failed: {done.stderr.strip()}")
    return done.stdout


def commit_exists(sha):
    if not COMMIT.fullmatch(sha or ""):
        return False
    done = git_result("cat-file", "-e", f"{sha}^{{commit}}")
    if done.returncode != 0:
        return False
    resolved = git("rev-parse", "--verify", f"{sha}^{{commit}}").strip()
    return resolved == sha


def ensure_commit(sha, fetch_refs, what):
    """Ensure exactly `sha` is in this repository without switching the caller's checkout."""
    if not COMMIT.fullmatch(sha or ""):
        raise Refused(f"{what} is not a full Git commit SHA: {sha!r}")
    if commit_exists(sha):
        return sha

    errors = []
    for ref in fetch_refs:
        if not ref:
            continue
        done = git_result("fetch", "--no-tags", "origin", ref)
        if done.returncode == 0 and commit_exists(sha):
            return sha
        errors.append(done.stderr.strip() or done.stdout.strip() or f"fetch {ref} failed")
    detail = "; ".join(e for e in errors if e)
    raise Refused(
        f"cannot obtain exact {what} {sha} without changing the checkout"
        + (f" ({detail})" if detail else "")
    )


def resolve_base(pull, requested):
    """Resolve the diff base once. The manifest records only the resulting immutable SHA."""
    if requested:
        done = git_result("rev-parse", "--verify", f"{requested}^{{commit}}")
        if done.returncode != 0:
            fetch = git_result("fetch", "--no-tags", "origin", requested)
            done = git_result("rev-parse", "--verify", f"{requested}^{{commit}}")
            if fetch.returncode != 0 or done.returncode != 0:
                raise Refused(
                    f"cannot resolve --base {requested!r} to one commit: "
                    f"{fetch.stderr.strip() or done.stderr.strip()}"
                )
        base = done.stdout.strip()
        if not COMMIT.fullmatch(base):
            raise Refused(f"--base {requested!r} resolved to non-commit identity {base!r}")
        return base

    base = pull.get("baseRefOid") or ""
    return ensure_commit(base, [pull.get("baseRefName")], "PR base commit")


@contextlib.contextmanager
def immutable_tree(head):
    """Yield a private detached worktree at `head`, removing only what this call created."""
    parent = pathlib.Path(tempfile.mkdtemp(prefix="rules-engine-review-tree-"))
    tree = parent / "tree"
    added = False
    cleanup_error = None
    try:
        git("worktree", "add", "--detach", "--quiet", str(tree), head)
        added = True
        actual = git("rev-parse", "HEAD", cwd=tree).strip()
        if actual != head:
            raise Refused(f"review worktree resolved to {actual}, not requested head {head}")
        yield tree
    finally:
        if added:
            done = git_result("worktree", "remove", "--force", str(tree))
            if done.returncode != 0:
                cleanup_error = done.stderr.strip() or done.stdout.strip()
                shutil.rmtree(tree, ignore_errors=True)
                git_result("worktree", "prune")
        if parent.exists():
            shutil.rmtree(parent, ignore_errors=True)
        if cleanup_error and sys.exc_info()[0] is None:
            raise Refused(f"could not remove temporary review worktree {tree}: {cleanup_error}")


def read_json(path, what):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError) as error:
        raise Refused(f"{what} cannot be read ({path}: {error})")


def policy(root):
    document = read_json(root / POLICY, POLICY)
    if not isinstance(document, dict):
        raise Refused(f"{POLICY} is not a JSON object")
    return document


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_path(path):
    try:
        return sha256_bytes(path.read_bytes())
    except OSError as error:
        raise Refused(f"cannot hash {path}: {error}")


def tracked_artifact(root, role, relative):
    path = root / relative
    if not path.is_file():
        raise Refused(f"reviewed commit has no {relative}; cannot bind {role}")
    return {"role": role, "path": relative, "sha256": sha256_path(path)}


def entry_ids(*texts):
    """Every entry id named by a marker in `texts`, in first-seen order."""
    found = []
    for text in texts:
        for part in (text or "").split(ENTRY_MARKER)[1:]:
            entry_id = part.split("-->")[0].strip()
            if entry_id and entry_id not in found:
                found.append(entry_id)
    return found


def entry_packet(entry_id, out_dir, reviewed_root, package_map=None):
    """Generate one entry packet with the reviewed commit's tool and capture its exact map input."""
    target = out_dir / f"entry-{entry_id}.md"
    identity = out_dir / f".entry-{entry_id}.identity.json"
    command = [
        sys.executable, str(reviewed_root / ENTRY_PACKET), entry_id,
        "--out", str(out_dir), "--identity-out", str(identity),
    ]
    if package_map:
        command += ["--package-map", package_map]
    done = subprocess.run(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=reviewed_root
    )
    if done.returncode != 0 or not target.is_file() or not identity.is_file():
        identity.unlink(missing_ok=True)
        return None, None, None, (
            done.stderr.strip() or "reviewed entry-packet.py produced no packet identity"
        )

    packet_digest = sha256_path(target)
    metadata = read_json(identity, f"entry packet identity for {entry_id}")
    identity.unlink(missing_ok=True)
    try:
        map_path = pathlib.Path(metadata["packageMapPath"])
        map_digest = metadata["packageMapSha256"]
        package_id = metadata["packageId"]
        package_version = metadata["packageVersion"]
        nupkg_digest = metadata.get("mapPackageSha256", "")
    except (KeyError, TypeError):
        return None, None, None, f"entry-packet.py returned malformed input identity for {entry_id}"
    if not SHA256.fullmatch(map_digest or ""):
        return None, None, None, f"entry-packet.py returned malformed package-map digest for {entry_id}"

    try:
        map_bytes = map_path.read_bytes()
    except OSError as error:
        return None, None, None, f"cannot re-read entry packet package map {map_path}: {error}"
    if sha256_bytes(map_bytes) != map_digest:
        return None, None, None, (
            f"package map changed while entry packet {entry_id} was assembled; refusing a mixed identity"
        )

    copy_name = f"package-map-{map_digest[:12]}.json"
    copy_path = out_dir / copy_name
    if copy_path.exists():
        if sha256_path(copy_path) != map_digest:
            return None, None, None, f"{copy_name} already exists with different bytes"
    else:
        copy_path.write_bytes(map_bytes)

    map_input = {
        "role": "package-map",
        "file": copy_name,
        "sha256": map_digest,
        "packageId": package_id,
        "packageVersion": package_version,
        "mapPackageSha256": nupkg_digest,
    }
    return target, packet_digest, map_input, None


def section(title, body):
    return f"## {title}\n\n{body.rstrip()}\n"


def bounded_diff(base, head):
    """The exact base/head diff, with a line budget."""
    text = git("diff", f"{base}...{head}")
    lines = text.splitlines()
    if len(lines) <= DIFF_LINE_BUDGET:
        return "```diff\n" + text.rstrip() + "\n```"
    kept = "\n".join(lines[:DIFF_LINE_BUDGET])
    return (
        "```diff\n" + kept + "\n```\n\n"
        f"**The diff is {len(lines)} lines and was cut at {DIFF_LINE_BUDGET}.** A change this size "
        f"against one issue is itself a finding: say so rather than reviewing the visible part and "
        f"calling it a review. The whole diff is reconstructable as `git diff {base}...{head}`."
    )


def build(number, base, out_dir, package_map=None):
    pull = json.loads(gh(
        "pr", "view", str(number), "--json",
        "number,title,body,headRefOid,headRefName,baseRefOid,baseRefName,files,closingIssuesReferences",
    ))
    head = pull.get("headRefOid") or ""
    ensure_commit(head, [f"pull/{number}/head", pull.get("headRefName")], "PR head commit")
    base_sha = resolve_base(pull, base)

    issues = pull.get("closingIssuesReferences") or []
    if len(issues) != 1:
        raise Refused(
            f"PR #{number} closes {len(issues)} issues; the rails allow exactly one (`AGENTS.md`). "
            "Fix the PR body before reviewing it."
        )
    issue_number = issues[0]["number"]
    issue = json.loads(gh(
        "issue", "view", str(issue_number), "--json", "number,title,body,labels,state"
    ))
    issue_labels = [label["name"] for label in issue.get("labels") or []]

    with immutable_tree(head) as reviewed_root:
        settings = policy(reviewed_root)
        labels = settings.get("labels") or {}
        review = settings.get("review") or {}
        risk = [
            label for label in issue_labels
            if label in (labels.get("normalRisk"), labels.get("independentRisk"))
        ]
        independent = labels.get("independentRisk") in issue_labels

        changed = [f["path"] for f in pull.get("files") or []]
        semantic = [
            path for path in changed if is_semantic(path, review.get("semanticPaths") or [])
        ]

        record = read_json(reviewed_root / PROVENANCE, PROVENANCE)
        entries = entry_ids(issue.get("body"), pull.get("body"))
        manifest_name = f"pr-{number}-{head[:12]}.review.json"

        parts = [
            f"# Review packet: PR #{number} — {pull.get('title', '')}\n",
            f"Head commit `{head}`. Base commit `{base_sha}`. **Every verdict is recorded "
            f"against this exact reviewed commit through `{manifest_name}`.** If the pull request "
            "gains another commit, this packet may remain historical evidence but satisfies no gate "
            "for the new head.\n",
            section(
                "1. The issue this closes",
                f"**#{issue_number} — {issue.get('title', '')}** ({issue.get('state', '')})\n\n"
                f"Labels: {', '.join(issue_labels) or 'none'}\n\n"
                f"Risk: {', '.join(risk) if risk else 'no risk label — that is itself a finding'}"
                + (
                    "\n\n**Independent review is required for this issue.** A semantic verdict "
                    "alone does not satisfy the gate."
                    if independent else ""
                )
                + f"\n\n---\n\n{issue.get('body') or '(empty)'}",
            ),
            section("2. What the pull request claims", pull.get("body") or
                    "(empty — the PR template is not optional)"),
        ]

        packets = []
        map_input = None
        if entries:
            rendered = []
            for entry_id in entries:
                path, digest, this_map, problem = entry_packet(
                    entry_id, out_dir, reviewed_root, package_map
                )
                if problem:
                    raise Refused(f"entry {entry_id}: {problem}")
                if map_input is None:
                    map_input = this_map
                elif this_map != map_input:
                    raise Refused(
                        "entry packets were assembled from different package-map identities; "
                        "one review packet may bind only one exact map input"
                    )
                packets.append((entry_id, path, digest))
                rendered.append(
                    f"- `{entry_id}`: `{path.name}` (sha256 `{digest}`)"
                )
            body = (
                "Read these **before** the diff. They are the map's own bytes for the entries this "
                "change names; your reading of the rule is formed from them, not from the "
                "implementation.\n\n" + "\n".join(rendered)
            )
        else:
            body = (
                "The issue and the pull request name no entry (no `rules-factory-entry` marker). "
                "For a change to the rules surface that is a finding: the reviewer cannot check an "
                "implementation against a rule nobody named."
            )
        parts.append(section("3. The entries, as the map has them", body))

        try:
            map_record = record["map"]
            factory_record = record["factory"]
        except (KeyError, TypeError):
            raise Refused("reviewed provenance.json does not name map and factory identity")
        parts.append(section(
            "4. What this engine was produced from",
            f"- map `{map_record['packageId']}` {map_record['version']} "
            f"(`sha256:{map_record.get('nupkgSha256', '')}`)\n"
            + "".join(
                f"- corpus `{c.get('sourceId')}`"
                + (" (principal)" if c.get("principal") else "")
                + f", {c.get('hashDerivation', '')}, content hash `{c.get('contentHash', '')}`\n"
                for c in record.get("corpora") or []
            )
            + f"- randomness declared: `{record.get('randomness')}`\n"
            + f"- factory `{factory_record.get('commit', '')[:12]}`",
        ))

        overlay_diff = git("diff", f"{base_sha}...{head}", "--", OVERLAY).rstrip()
        parts.append(section(
            "5. The overlay, before and after",
            (
                "```diff\n" + overlay_diff + "\n```\n\nEvery test named here carries the "
                "mutation that makes it fail. A mutation too vague to re-run is a finding."
            ) if overlay_diff else (
                f"`{OVERLAY}/` is unchanged. A change that adds a test without naming it here, "
                "or implements an entry without moving its status, is a finding."
            ),
        ))

        parts.append(section(
            "6. What changed",
            "\n".join(
                f"- `{path}`" + ("  ← semantic surface" if path in semantic else "")
                for path in changed
            ) or "(no files)",
        ))
        parts.append(section("7. The diff", bounded_diff(base_sha, head)))
        parts.append(section(
            "8. Determinism",
            "Check, in the diff above: wall-clock time; ambient locale, culture or encoding; "
            "environment-dependent ordering (dictionary or set iteration, file-system order); "
            "unseeded randomness; hash codes or object identity in anything observable; anything "
            "that reads the machine rather than the request. The engine's declared randomness is "
            "in section 4: an engine declaring `none` may not reference a randomness package at all.",
        ))

        gates = [
            "- `validate` — `./scripts/validate.sh full`",
            (
                f"- `{review.get('semanticContext', '(unset)')}` — required for this change"
                if semantic else
                f"- `{review.get('semanticContext', '(unset)')}` — not required: nothing here "
                "touches the semantic surface"
            ),
        ]
        if independent:
            chain = " → ".join(
                link.get("context", "?") for link in review.get("independentFallback") or []
            )
            gates.append(
                f"- one of: {chain} — required, because the issue is "
                f"{labels.get('independentRisk')}"
            )
        parts.append(section(
            "9. What must be green before this merges",
            "\n".join(gates)
            + f"\n\nRecord a verdict with `tools/record-verdict.py --pr {number} --packet "
            f"<packet-dir>/{manifest_name} --reviewer <id> --verdict pass|fail`. The manifest, not "
            "the current PR head, decides what commit was reviewed. A later head makes this packet "
            "stale for the gate; it never retargets the verdict. The fallback chain advances only "
            "when a provider is unavailable — never because its verdict was unwelcome.",
        ))

        artifacts = [
            tracked_artifact(reviewed_root, "policy", POLICY),
            tracked_artifact(reviewed_root, "provenance", PROVENANCE),
            tracked_artifact(reviewed_root, "entry-packet-tool", ENTRY_PACKET),
        ]

    return "\n".join(parts), head, base_sha, packets, artifacts, map_input


def is_semantic(path, patterns):
    """Whether `path` is on the semantic surface, by the policy's glob patterns."""
    for pattern in patterns:
        regex = (
            re.escape(pattern)
            .replace(r"\*\*/", "(?:.*/)?")
            .replace(r"\*\*", ".*")
            .replace(r"\*", "[^/]*")
        )
        if re.fullmatch(regex, path):
            return True
    return False


def destination(out):
    if out is None:
        root = os.environ.get(PACKET_ROOT_VARIABLE) or os.path.join(
            tempfile.gettempdir(), "rules-engine-packets"
        )
        out = os.path.join(root, ROOT.name)
    resolved = pathlib.Path(out).expanduser().resolve()
    if resolved == ROOT or ROOT in resolved.parents:
        raise Refused(
            f"a packet is never written inside the repository ({resolved}); use --out elsewhere, "
            f"or ${PACKET_ROOT_VARIABLE}"
        )
    return resolved


def canonical_identity(document):
    payload = {key: value for key, value in document.items() if key != "identitySha256"}
    data = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return sha256_bytes(data)


def manifest_for(number, head, base, packet_path, packets, artifacts, map_input):
    entry_packets = [
        {"entryId": entry_id, "file": path.name, "sha256": digest}
        for entry_id, path, digest in sorted(packets, key=lambda item: item[0])
    ]
    document = {
        "reviewPacketFormat": 1,
        "pullRequest": number,
        "reviewedCommit": head,
        "baseCommit": base,
        "packet": {"file": packet_path.name, "sha256": sha256_path(packet_path)},
        "artifacts": sorted(artifacts, key=lambda item: (item["role"], item["path"])),
        "entryPackets": entry_packets,
        "inputs": [map_input] if map_input else [],
    }
    document["identitySha256"] = canonical_identity(document)
    return document


def write_json(path, document):
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="review-packet.py", description=__doc__.split("\n")[0]
    )
    parser.add_argument("pr", type=int, help="the pull request number")
    parser.add_argument(
        "--out",
        help=f"directory to write into (default: ${PACKET_ROOT_VARIABLE}, else a directory "
             "beside the system temporary one)",
    )
    parser.add_argument(
        "--package-map",
        help="the restored map package's corpus-map.json, passed to the reviewed entry-packet.py "
             "(default: that tool asks MSBuild)",
    )
    parser.add_argument(
        "--base",
        help="optional diff base ref; resolved once to a commit (default: the PR's base commit OID)",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="write only the human packet to stdout; no durable review bundle is emitted",
    )
    args = parser.parse_args(argv)

    stage = pathlib.Path(tempfile.mkdtemp(prefix="rules-engine-review-output-"))
    try:
        text, head, base, packets, artifacts, map_input = build(
            args.pr, args.base, stage, args.package_map
        )
        if args.stdout:
            sys.stdout.write(text)
            return 0

        out_dir = destination(args.out)
        packet_name = f"pr-{args.pr}-{head[:12]}.md"
        packet_path = stage / packet_name
        packet_path.write_text(text, encoding="utf-8")
        manifest = manifest_for(
            args.pr, head, base, packet_path, packets, artifacts, map_input
        )
        manifest_path = stage / f"pr-{args.pr}-{head[:12]}.review.json"
        write_json(manifest_path, manifest)

        out_dir.mkdir(parents=True, exist_ok=True)
        names = [packet_path.name, manifest_path.name]
        names += [path.name for _, path, _ in packets]
        if map_input:
            names.append(map_input["file"])
        names = list(dict.fromkeys(names))
        for name in names:
            shutil.copyfile(stage / name, out_dir / name)

        print(out_dir / packet_path.name)
        print(out_dir / manifest_path.name)
        for _, path, _ in packets:
            print(out_dir / path.name)
        if map_input:
            print(out_dir / map_input["file"])
        return 0
    except Refused as error:
        print(f"review-packet: REFUSED -- {error}", file=sys.stderr)
        return 1
    finally:
        shutil.rmtree(stage, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
