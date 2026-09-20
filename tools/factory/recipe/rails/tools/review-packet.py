#!/usr/bin/env python3
"""Everything a reviewer needs about one pull request, assembled from one immutable commit.

    tools/review-packet.py <pr-number> [--out DIR] [--stdout] [--base main]

Emitted by rules-factory as a managed file (decision 0029). `AGENTS.md` is the contract, and
`docs/agent-team.md` says which reviewer reads what.

A saved review packet is evidence, not merely prose. The tool resolves the PR head and diff base
once, makes a detached temporary worktree at that exact head, and reads every repository artifact
from that immutable tree. It also writes a deterministic JSON identity manifest beside the human
Markdown. `tools/record-verdict.py` consumes that manifest; it never infers what was reviewed from
the PR's later head.

The caller's branch, index and uncommitted files are never switched or read as review evidence.
Temporary worktrees and staging directories are removed on success and failure.

`--stdout` is a preview only. It prints the human packet but deliberately emits no identity
manifest, so it cannot authorize a verdict.

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
PACKET_FORMAT = 1
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class Refused(Exception):
    """Something the packet cannot honestly assemble. Nothing is published."""


def gh(*args):
    command = [os.environ.get("RULES_ENGINE_GH", "gh"), *args]
    try:
        done = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                              cwd=ROOT, timeout=120)
    except (OSError, subprocess.SubprocessError) as error:
        raise Refused(f"cannot run {command[0]} ({error}); it is how a packet reads the issue and the PR")
    if done.returncode != 0:
        raise Refused(f"{' '.join(command)} failed: {done.stderr.strip() or done.stdout.strip()}")
    return done.stdout


def git_run(*args, cwd=ROOT, check=True):
    done = subprocess.run(["git", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          cwd=cwd, text=True)
    if check and done.returncode != 0:
        raise Refused(f"git {' '.join(args)} failed: {done.stderr.strip() or done.stdout.strip()}")
    return done


def git(*args, cwd=ROOT):
    return git_run(*args, cwd=cwd).stdout.strip()


def git_bytes(*args, cwd=ROOT):
    done = subprocess.run(["git", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd)
    if done.returncode != 0:
        raise Refused(f"git {' '.join(args)} failed: {done.stderr.decode('utf-8', 'replace').strip()}")
    return done.stdout


def ensure_commit(number, sha):
    """Ensure GitHub's exact reviewed SHA exists locally without switching the caller's checkout."""
    if not SHA_RE.fullmatch(sha):
        raise Refused(f"PR #{number} reported {sha!r}, not a 40-character commit SHA")
    if git_run("cat-file", "-e", f"{sha}^{{commit}}", check=False).returncode == 0:
        return

    attempts = [f"pull/{number}/head", sha]
    errors = []
    for spec in attempts:
        done = git_run("fetch", "--no-tags", "origin", spec, check=False)
        if done.returncode != 0:
            errors.append(done.stderr.strip() or done.stdout.strip())
        if git_run("cat-file", "-e", f"{sha}^{{commit}}", check=False).returncode == 0:
            return
    detail = "; ".join(error for error in errors if error) or "the object is still absent after fetch"
    raise Refused(f"cannot obtain exact reviewed commit {sha} for PR #{number}: {detail}. "
                  "The packet will not fall back to the caller's checkout.")


@contextlib.contextmanager
def immutable_tree(number, sha):
    """A detached worktree pinned to sha, removed by exact path on every exit."""
    ensure_commit(number, sha)
    parent = pathlib.Path(tempfile.mkdtemp(prefix="rules-review-tree-"))
    tree = parent / "tree"
    added = False
    try:
        done = git_run("worktree", "add", "--detach", str(tree), sha, check=False)
        if done.returncode != 0:
            raise Refused(f"cannot create immutable worktree for {sha}: "
                          f"{done.stderr.strip() or done.stdout.strip()}")
        added = True
        actual = git("rev-parse", "HEAD", cwd=tree)
        if actual != sha:
            raise Refused(f"immutable worktree resolved to {actual}, not reviewed commit {sha}")
        yield tree
    finally:
        if added:
            removed = git_run("worktree", "remove", "--force", str(tree), check=False)
            if removed.returncode != 0:
                git_run("worktree", "prune", check=False)
        if parent.exists():
            shutil.rmtree(parent, ignore_errors=True)


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    return sha256_bytes(path.read_bytes())


def canonical_digest(value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256_bytes(data)


def policy(root):
    try:
        return json.loads((root / POLICY).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise Refused(f"{POLICY} cannot be read from reviewed commit ({error}); "
                      "it holds the labels and review contexts")


def source_identity(root, role, relative):
    path = root / relative
    try:
        data = path.read_bytes()
    except OSError as error:
        raise Refused(f"review source {relative} cannot be read from reviewed commit ({error})")
    return {"role": role, "path": relative, "sha256": sha256_bytes(data)}


def entry_ids(*texts):
    found = []
    for text in texts:
        for part in (text or "").split(ENTRY_MARKER)[1:]:
            entry_id = part.split("-->")[0].strip()
            if entry_id and entry_id not in found:
                found.append(entry_id)
    return found


def entry_packet(root, entry_id, out_dir, package_map=None):
    """Generate one entry packet using the reviewed tree's implementation and inputs."""
    target = out_dir / f"entry-{entry_id}.md"
    command = [sys.executable, str(root / ENTRY_PACKET), entry_id, "--out", str(out_dir)]
    if package_map:
        command += ["--package-map", package_map]
    done = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=root)
    if done.returncode != 0 or not target.is_file():
        return None, None, (done.stderr.strip() or "entry-packet.py produced nothing")
    return target, sha256_file(target), None


def section(title, body):
    return f"## {title}\n\n{body.rstrip()}\n"


def diff_text(base_sha, head, *paths):
    args = ["diff", f"{base_sha}...{head}"]
    if paths:
        args += ["--", *paths]
    return git(*args)


def bounded_diff(base_sha, head):
    text = diff_text(base_sha, head)
    lines = text.splitlines()
    if len(lines) <= DIFF_LINE_BUDGET:
        return "```diff\n" + text.rstrip() + "\n```"
    kept = "\n".join(lines[:DIFF_LINE_BUDGET])
    return ("```diff\n" + kept + "\n```\n\n"
            f"**The diff is {len(lines)} lines and was cut at {DIFF_LINE_BUDGET}.** A change this size against one "
            f"issue is itself a finding: say so rather than reviewing the visible part and calling it a review. "
            f"The exact diff is `git diff {base_sha}...{head}`.")


def is_semantic(path, patterns):
    for pattern in patterns:
        regex = re.escape(pattern).replace(r"\*\*/", "(?:.*/)?").replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
        if re.fullmatch(regex, path):
            return True
    return False


def build(number, base, out_dir, package_map=None):
    external_inputs = []
    staged_package_map = None
    if package_map:
        source = pathlib.Path(package_map).expanduser().resolve()
        try:
            data = source.read_bytes()
        except OSError as error:
            raise Refused(f"external package map cannot be read ({source}): {error}")
        staged_package_map = out_dir / "package-map.json"
        staged_package_map.write_bytes(data)
        external_inputs.append({"role": "package-map", "file": staged_package_map.name,
                                "sha256": sha256_bytes(data)})

    pull = json.loads(gh("pr", "view", str(number), "--json",
                         "number,title,body,headRefOid,headRefName,baseRefName,files,closingIssuesReferences"))
    head = pull.get("headRefOid") or ""
    if not SHA_RE.fullmatch(head):
        raise Refused(f"PR #{number} has no exact 40-character head commit")
    base_sha = git("rev-parse", f"{base}^{{commit}}")
    if not SHA_RE.fullmatch(base_sha):
        raise Refused(f"base {base!r} did not resolve to one commit")

    issues = pull.get("closingIssuesReferences") or []
    if len(issues) != 1:
        raise Refused(f"PR #{number} closes {len(issues)} issues; the rails allow exactly one (`AGENTS.md`). "
                      "Fix the PR body before reviewing it.")
    issue_number = issues[0]["number"]
    issue = json.loads(gh("issue", "view", str(issue_number), "--json", "number,title,body,labels,state"))

    with immutable_tree(number, head) as reviewed:
        settings = policy(reviewed)
        labels = settings.get("labels") or {}
        review = settings.get("review") or {}
        issue_labels = [label["name"] for label in issue.get("labels") or []]
        risk = [label for label in issue_labels
                if label in (labels.get("normalRisk"), labels.get("independentRisk"))]
        independent = labels.get("independentRisk") in issue_labels

        changed = [f["path"] for f in pull.get("files") or []]
        semantic = [path for path in changed if is_semantic(path, review.get("semanticPaths") or [])]

        try:
            record_bytes = (reviewed / PROVENANCE).read_bytes()
            record = json.loads(record_bytes.decode("utf-8"))
        except (OSError, ValueError) as error:
            raise Refused(f"{PROVENANCE} cannot be read from reviewed commit {head[:12]} ({error})")

        entries = entry_ids(issue.get("body"), pull.get("body"))
        parts = [
            f"# Review packet: PR #{number} — {pull.get('title', '')}\n",
            f"Reviewed commit `{head}`. Resolved diff base `{base_sha}`. "
            "**Every verdict from this packet belongs only to this immutable commit.** "
            "If the pull request advances, the packet remains historical evidence and satisfies no gate for the new head.\n",
            section("1. The issue this closes",
                    f"**#{issue_number} — {issue.get('title', '')}** ({issue.get('state', '')})\n\n"
                    f"Labels: {', '.join(issue_labels) or 'none'}\n\n"
                    f"Risk: {', '.join(risk) if risk else 'no risk label — that is itself a finding'}"
                    + ("\n\n**Independent review is required for this issue.** A semantic verdict alone does not "
                       "satisfy the gate." if independent else "") +
                    f"\n\n---\n\n{issue.get('body') or '(empty)'}"),
            section("2. What the pull request claims", pull.get("body") or "(empty — the PR template is not optional)")
        ]

        packet_artifacts = []
        if entries:
            rendered = []
            for entry_id in entries:
                path, digest, problem = entry_packet(reviewed, entry_id, out_dir,
                                                     str(staged_package_map) if staged_package_map else None)
                if problem:
                    raise Refused(f"entry packet for {entry_id} could not be assembled from reviewed commit "
                                  f"{head[:12]}: {problem}")
                else:
                    packet_artifacts.append({"role": "entry-packet", "entryId": entry_id,
                                             "file": path.name, "sha256": digest})
                    rendered.append(f"- `{entry_id}`: `{path.name}` (sha256 `{digest}`)")
            body = ("Read these **before** the diff. They are the map's own bytes for the entries this change names; "
                    "your reading of the rule is formed from them, not from the implementation.\n\n"
                    + "\n".join(rendered))
        else:
            body = ("The issue and the pull request name no entry (no `rules-factory-entry` marker). For a change "
                    "to the rules surface that is a finding: the reviewer cannot check an implementation against a "
                    "rule nobody named.")
        parts.append(section("3. The entries, as the map has them", body))

        parts.append(section("4. What this engine was produced from",
                             f"- map `{record['map']['packageId']}` {record['map']['version']} "
                             f"(`sha256:{record['map'].get('nupkgSha256', '')}`)\n"
                             + "".join(
                                 f"- corpus `{c.get('sourceId')}`"
                                 + (" (principal)" if c.get("principal") else "")
                                 + f", {c.get('hashDerivation', '')}, content hash `{c.get('contentHash', '')}`\n"
                                 for c in record.get("corpora") or [])
                             + f"- randomness declared: `{record.get('randomness')}`\n"
                             + f"- factory `{record['factory'].get('commit', '')[:12]}`"))

        overlay_diff = diff_text(base_sha, head, OVERLAY).rstrip()
        parts.append(section("5. The overlay, before and after",
                             ("```diff\n" + overlay_diff + "\n```\n\nEvery test named here carries the mutation "
                              "that makes it fail. A mutation too vague to re-run is a finding.")
                             if overlay_diff else
                             f"`{OVERLAY}/` is unchanged. A change that adds a test without naming it here, or "
                             "implements an entry without moving its status, is a finding."))

        parts.append(section("6. What changed",
                             "\n".join(f"- `{path}`" + ("  ← semantic surface" if path in semantic else "")
                                       for path in changed) or "(no files)"))
        parts.append(section("7. The diff", bounded_diff(base_sha, head)))
        parts.append(section("8. Determinism",
                             "Check, in the diff above: wall-clock time; ambient locale, culture or encoding; "
                             "environment-dependent ordering (dictionary or set iteration, file-system order); "
                             "unseeded randomness; hash codes or object identity in anything observable; anything "
                             "that reads the machine rather than the request. The engine's declared randomness is in "
                             "section 4: an engine declaring `none` may not reference a randomness package at all."))

        gates = ["- `validate` — `./scripts/validate.sh full`",
                 f"- `{review.get('semanticContext', '(unset)')}` — required for this change"
                 if semantic else
                 f"- `{review.get('semanticContext', '(unset)')}` — not required: nothing here touches the semantic surface"]
        if independent:
            chain = " → ".join(link.get("context", "?") for link in review.get("independentFallback") or [])
            gates.append(f"- one of: {chain} — required, because the issue is {labels.get('independentRisk')}")
        parts.append(section("9. What must be green before this merges",
                             "\n".join(gates) +
                             "\n\nA saved verdict is recorded from this packet's JSON identity manifest, on the reviewed "
                             "commit above. A later head never inherits it. The chain advances only when a provider is "
                             "unavailable — never because its verdict was unwelcome."))

        sources = [
            source_identity(reviewed, "provenance", PROVENANCE),
            source_identity(reviewed, "policy", POLICY),
        ]
        if entries:
            sources.append(source_identity(reviewed, "entry-packet-tool", ENTRY_PACKET))

        map_identity = {
            "packageId": record["map"].get("packageId"),
            "version": record["map"].get("version"),
            "nupkgSha256": record["map"].get("nupkgSha256", ""),
        }
        context = {
            "pullRequestSha256": canonical_digest({
                key: pull.get(key) for key in
                ("number", "title", "body", "headRefOid", "headRefName", "baseRefName", "files",
                 "closingIssuesReferences")
            }),
            "issueSha256": canonical_digest({
                key: issue.get(key) for key in ("number", "title", "body", "labels", "state")
            }),
        }

    full_diff_digest = sha256_bytes(git_bytes("diff", f"{base_sha}...{head}"))
    return ("\n".join(parts), head, base_sha, full_diff_digest, packet_artifacts, sources,
            external_inputs, map_identity, context)


def destination(out):
    if out is None:
        root = os.environ.get(PACKET_ROOT_VARIABLE) or os.path.join(tempfile.gettempdir(), "rules-engine-packets")
        out = os.path.join(root, ROOT.name)
    resolved = pathlib.Path(out).expanduser().resolve()
    if resolved == ROOT or ROOT in resolved.parents:
        raise Refused(f"a packet is never written inside the repository ({resolved}); use --out elsewhere, or "
                      f"${PACKET_ROOT_VARIABLE}")
    return resolved


def manifest_for(number, head, base_sha, diff_digest, packet_path, artifacts, sources, inputs,
                 map_identity, context):
    return {
        "formatVersion": PACKET_FORMAT,
        "pullRequest": number,
        "reviewedCommit": head,
        "baseCommit": base_sha,
        "diffSha256": diff_digest,
        "packet": {"file": packet_path.name, "sha256": sha256_file(packet_path)},
        "map": map_identity,
        "sources": sorted(sources, key=lambda item: (item["role"], item["path"])),
        "inputs": sorted(inputs, key=lambda item: (item["role"], item["file"])),
        "artifacts": sorted(artifacts, key=lambda item: (item["role"], item["file"])),
        "context": context,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(prog="review-packet.py", description=__doc__.split("\n")[0])
    parser.add_argument("pr", type=int, help="the pull request number")
    parser.add_argument("--out", help=f"directory to write into (default: ${PACKET_ROOT_VARIABLE}, else a "
                                      "directory beside the system temporary one)")
    parser.add_argument("--package-map", help="the restored map package's corpus-map.json, passed to "
                                              "entry-packet.py")
    parser.add_argument("--base", default="origin/main",
                        help="ref resolved once to the immutable diff base (default: origin/main)")
    parser.add_argument("--stdout", action="store_true",
                        help="preview the human packet; emits no manifest and cannot authorize a verdict")
    args = parser.parse_args(argv)

    stage = pathlib.Path(tempfile.mkdtemp(prefix="rules-review-packet-"))
    try:
        out_dir = destination(args.out)
        text, head, base_sha, diff_digest, artifacts, sources, inputs, map_identity, context = build(
            args.pr, args.base, stage, args.package_map)
        if args.stdout:
            sys.stdout.write(text)
            return 0

        packet = stage / f"pr-{args.pr}-{head[:12]}.md"
        packet.write_text(text, encoding="utf-8")
        manifest = stage / f"pr-{args.pr}-{head[:12]}.review.json"
        document = manifest_for(args.pr, head, base_sha, diff_digest, packet, artifacts, sources,
                                inputs, map_identity, context)
        manifest.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        out_dir.mkdir(parents=True, exist_ok=True)
        publish = ([packet] + [stage / item["file"] for item in artifacts]
                   + [stage / item["file"] for item in inputs] + [manifest])
        published = []
        for source in publish:
            target = out_dir / source.name
            os.replace(source, target)
            published.append(target)
    except Refused as error:
        print(f"review-packet: REFUSED -- {error}", file=sys.stderr)
        return 1
    finally:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)

    for path in published:
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
