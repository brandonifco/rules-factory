#!/usr/bin/env python3
"""What a semantic review covered, what a repair invalidates of it, and the bounded review that follows.

    tools/review-scope.py delta <pr> --prior <reviews/attestations/...json> --package-map PATH [--out DIR]
    tools/review-scope.py impact --prior <path> [--commit REF] [--entry ID ...] --package-map PATH [--json]
    tools/review-scope.py state [--commit REF] [--entry ID ...] --package-map PATH
    tools/review-scope.py self-review <entry id> [--commit REF] --package-map PATH [--check]
    tools/review-scope.py ruling-review <decision record path> [--commit REF] [--check]
    tools/review-scope.py verify <attestation path> [--commit REF]
    tools/review-scope.py telemetry [<attestation> ...]

Emitted by rules-factory as a managed file (rules-factory decision 0071). `AGENTS.md` section 7 is
the contract, and `docs/review-evidence.md` says how to read what this writes.

**Why.** A verdict binds one head (0053), and until this existed nothing recorded what it had
covered: a repair commit ended the verdict, and the next review reread the whole slice. A chain of
eight repairs paid for eight complete rereads, most of them of bytes the repairs never touched.

So a review now leaves an attestation (`tools/record-verdict.py` writes it) naming every claim it
covered and the fingerprint of every unit each claim rests on -- the map entry and its overlay
row, the entries it depends on, the corpus it cites, and the implementation and test files a
lexical reference graph of the engine's C# reaches from it. This tool compares those fingerprints
with the new head and says, claim by claim, what the repair invalidated and why. It never takes
anybody's word that a change is isolated. `delta` then writes the packet that review reads: the
invalidated claims, their entries, the diff since the prior head within their closure, the
blocking findings being repaired, and nothing else -- no conversation, because none is needed.

**A full review needs a reason.** When the change cannot be bounded -- the charter, the policy, a
corpus, a map's frame, a foundational file or a decision record moved; a file the graph cannot
read changed; the repair invalidated too much -- `delta` refuses and prints the reasons, and
`tools/review-packet.py <pr> --role semantic --prior <attestation> --package-map <path>` writes the full packet that answers them. That the
head changed is never one of them.

**Integrity.** The prior attestation is read from the reviewed commit, where the repair committed
it under `reviews/attestations/`, and its SHA-256 must be the one `tools/record-verdict.py` put in
the commit status at the prior head. An attestation edited after it was recorded does not match,
and is not reused: the review is a full one, and says why.

**Nothing is written into the repository**, and a refusal writes nothing at all: packets go to
`$RULES_ENGINE_PACKET_ROOT` or a directory beside the system temporary one, as every packet does.

Standard library only, plus `gh` (or `$RULES_ENGINE_GH`), `git`, and the factory's own model,
vendored as `scripts/factory/reviewscope.py`.
"""
import argparse
import glob
import hashlib
import importlib.util
import json
import os
import pathlib
import subprocess
import sys

# The vendored factory modules are imported from scripts/factory, and an import leaves bytecode
# beside the module unless this is set first (#194).
sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROVENANCE = "provenance.json"
POLICY = ".github/agent-policy.json"


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def vendored(name):
    sys.path.insert(0, str(ROOT / "scripts" / "factory"))
    try:
        return __import__(name)
    except ImportError as error:
        raise Refused(f"scripts/factory/{name}.py is not importable ({error}); run `factory produce` again")


class Refused(Exception):
    """Something this cannot honestly compute. Nothing is written."""


# The packet plumbing -- `gh`, the reviewed snapshot, the map read once and checked, the entry
# packets -- is review-packet.py's, and one copy of it is what keeps a delta packet's evidence
# bound exactly as a full packet's is (0053, 0057).
PACKET = _module("review_packet_for_scope", pathlib.Path(__file__).resolve().parent / "review-packet.py")


def scope_model():
    return vendored("reviewscope")


# --- the state of the engine at one commit ---------------------------------------------------


def tracked(snapshot):
    """Every tracked file of the engine in `snapshot`, engine-relative."""
    done = subprocess.run(["git", "ls-files", "-z"], cwd=snapshot, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if done.returncode != 0:
        raise Refused(f"git ls-files failed in the reviewed snapshot: {done.stderr.decode().strip()}")
    return sorted(p for p in done.stdout.decode("utf-8").split("\0") if p)


def read_json(path, what):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise Refused(f"{what} cannot be read ({error})")


def engine_state(snapshot, checked_maps, slice_entries):
    """(model, state, facts) for the engine in `snapshot`, built from the maps in `checked_maps`.

    `checked_maps` are the copies `PACKET.maps_read_once` made of map bytes already held to the
    digests the snapshot's provenance declares; nothing else is read as a map.
    """
    model = scope_model()
    compose = vendored("compose")
    overlay_step = vendored("overlay")
    record = read_json(snapshot / PROVENANCE, PROVENANCE)
    packages = PACKET.map_packages(record)
    documents = [read_json(path, "a checked map") for path in checked_maps]
    try:
        package = compose.union([(p["packageId"], d) for p, d in zip(packages, documents)])
    except compose.Refused as error:
        raise Refused(f"the maps this engine was produced from do not compose: {error}")
    try:
        overlay = overlay_step.load(str(snapshot), package)
    except overlay_step.OverlayError as error:
        raise Refused(str(error))
    entries = {str(e["id"]): {"entry": e, "overlay": overlay.get(str(e["id"]))}
               for e in package.get("entries") or [] if isinstance(e, dict) and e.get("id")}
    unknown = [e for e in slice_entries if e not in entries]
    if unknown:
        raise Refused(f"the slice names {', '.join(unknown)}, which the merged map does not hold")
    files = {path: (snapshot / path).read_bytes() for path in tracked(snapshot)
             if model.classify(path) in ("implementation", "generated", "foundational", "decision", "unreadable")}
    try:
        policy = json.loads((snapshot / POLICY).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise Refused(f"{POLICY} cannot be read at the reviewed commit ({error})")
    charter = snapshot / model.CHARTER
    invariants_path = snapshot / model.INVARIANTS
    invariants = (read_json(invariants_path, model.INVARIANTS).get("invariants") or []
                  if invariants_path.is_file() else [])
    maps = []
    for package_record, document, path in zip(packages, documents, checked_maps):
        maps.append({"packageId": package_record["packageId"], "version": package_record.get("version"),
                     "sha256": hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest(),
                     "frame": {k: v for k, v in document.items() if k != "entries"}})
    snap = model.Snapshot(
        entries=entries, slice=slice_entries, files=files, maps=maps,
        corpora={c["sourceId"]: c.get("contentHash") for c in record.get("corpora") or [] if isinstance(c, dict)},
        charter=hashlib.sha256(charter.read_bytes()).hexdigest() if charter.is_file() else "absent",
        policy_review=model.fingerprint(policy.get("review") or {}),
        factory=str((record.get("factory") or {}).get("commit") or ""),
        generated_recorded={g["path"]: g.get("sha256") for g in record.get("generated") or []
                            if isinstance(g, dict) and "path" in g},
        invariants=invariants,
        # The generator's own member names, reserved-word suffix and all, so an entry reached through
        # its generated request type is recognised by the name the build gives it.
        members={entry_id: vendored("semantics").pascal(entry_id) for entry_id in entries})
    current = model.state(snap)
    facts = {
        "project": {"engine": (record.get("engine") or {}).get("name"),
                    "enginePath": (record.get("repository") or {}).get("enginePath") or ""},
        "maps": [{k: m[k] for k in ("packageId", "version", "sha256")} for m in maps],
        "corpora": [{"sourceId": s, "contentHash": h} for s, h in sorted(snap.corpora.items())],
        "charter": {"path": model.CHARTER, "sha256": snap.charter},
        "locators": {e: (entries[e]["entry"].get("locator")) for e in slice_entries},
        "tests": {e: (entries[e]["overlay"] or {}).get("tests") or [] for e in slice_entries},
        "declaredTests": model.declared_tests(files),
        "policy": policy,
    }
    return model, current, facts


# --- the prior attestation --------------------------------------------------------------------


def recorded_digests(sha):
    """Every attestation digest a status at `sha` names: what the recorder wrote, read back."""
    repository = json.loads(PACKET.gh("repo", "view", "--json", "nameWithOwner"))["nameWithOwner"]
    statuses = json.loads(PACKET.gh("api", f"repos/{repository}/commits/{sha}/statuses?per_page=100"))
    found = set()
    for status in statuses if isinstance(statuses, list) else []:
        words = str(status.get("description") or "").split()
        for index, word in enumerate(words[:-1]):
            if word == "attestation":
                found.add(words[index + 1].strip(";,."))
    return found


def load_prior(snapshot, path, head):
    """(the prior attestation, whether it may be reused, why not) -- read from the reviewed commit.

    Reused only when it is committed at `head`, is well formed, is of an ancestor of `head`, names
    the maps and engine that commit declared, and hashes to a digest recorded at that commit.
    Anything less is not an error to stop at: it is a prior that cannot be reused, which is a full
    review with the reason `prior-attestation-unusable` (0071 part 4).
    """
    model = scope_model()
    relative = pathlib.PurePosixPath(path)
    if relative.is_absolute() or ".." in relative.parts or not str(relative).startswith(model.ATTESTATIONS + "/"):
        raise Refused(f"--prior {path} is not a path under {model.ATTESTATIONS}/: the prior attestation is read from "
                      f"the reviewed commit, where the repair committed it, and nowhere else")
    source = snapshot / str(relative)
    if not source.is_file():
        raise Refused(f"{path} is not committed at {head[:12]}. The repair commits the attestation it answers "
                      f"(`tools/record-verdict.py` printed where it wrote it) under {model.ATTESTATIONS}/, so the "
                      f"repository alone says what was reviewed")
    raw = source.read_bytes()
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        return None, False, f"{path} is not JSON ({error})"
    problems = model.validate_attestation(document)
    if problems:
        return document, False, "; ".join(problems[:3])
    prior_commit = document["reviewedCommit"]
    ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", prior_commit, head], cwd=PACKET.ROOT,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if ancestor.returncode != 0:
        return document, False, f"{prior_commit[:12]} is not an ancestor of {head[:12]}"
    try:
        at_prior = json.loads(PACKET.git("show", f"{prior_commit}:{(PACKET.engine_path() + '/') if PACKET.engine_path() else ''}{PROVENANCE}"))
    except (PACKET.Refused, ValueError) as error:
        return document, False, f"{PROVENANCE} at {prior_commit[:12]} cannot be read ({error})"
    maps = [{"packageId": m.get("packageId"),
             "sha256": next((f.get("sha256") for f in m.get("files") or [] if f.get("role") == "map"), None)}
            for m in PACKET.map_packages(at_prior)]
    try:
        recorded = recorded_digests(prior_commit)
    except (PACKET.Refused, ValueError, KeyError) as error:
        return document, False, f"the statuses at {prior_commit[:12]} cannot be read ({error}), so its integrity is NOT CHECKED"
    digest = model.attestation_digest(document)
    # The prior is the *latest* review, not any ancestor's: a review recorded after it -- a delta that
    # failed, even at a commit a later revert took back -- would otherwise be skipped by naming an
    # older PASS, and its findings with it.
    try:
        later = []
        for commit in PACKET.git("rev-list", f"{prior_commit}..{head}").split():
            found = recorded_digests(commit) - {digest}
            if found:
                later.append(f"{commit[:12]} ({', '.join(sorted(d[:12] for d in found))})")
    except (PACKET.Refused, ValueError, KeyError) as error:
        return document, False, f"the statuses after {prior_commit[:12]} cannot be read ({error}), so whether this is the latest review is NOT CHECKED"
    if later:
        return document, False, (f"a later review was recorded after {prior_commit[:12]}, at {'; '.join(later)}: the "
                                 f"prior is the latest attestation, and its findings are not skipped by naming an older one")
    problems = model.check_binding(document, recorded_digest=digest if digest in recorded else "none recorded",
                                   reviewed_commit=prior_commit, maps=maps,
                                   project=(at_prior.get("engine") or {}).get("name"))
    if problems:
        return document, False, "; ".join(problems)
    return document, True, None


# --- the commands -----------------------------------------------------------------------------


def snapshot_for(ref):
    head = PACKET.git("rev-parse", f"{ref}^{{commit}}").strip()
    parent, snapshot = PACKET.reviewed_snapshot(head)
    return head, parent, snapshot


def checked(package_maps, snapshot, head, parent):
    record = read_json(snapshot / PROVENANCE, PROVENANCE)
    if not package_maps:
        raise Refused("--package-map is required: the entries a claim rests on are read from the map, and the map "
                      "is held to the digest the reviewed commit declares (0057). Pass the restored package's "
                      "corpus-map.json, once per package of a composed engine.")
    _, copies = PACKET.maps_read_once([str(pathlib.Path(p).expanduser().resolve()) for p in package_maps],
                                      record, head, parent)
    return copies


def ceiling_of(policy, model):
    value = (policy.get("review") or {}).get("deltaCeiling", model.DEFAULT_DELTA_CEILING)
    return value if isinstance(value, (int, float)) and 0 < value <= 1 else model.DEFAULT_DELTA_CEILING


def recompute(head, prior_path, package_maps, entries):
    """(prior, impact) at `head`, computed afresh from the repository: what a carry is posted on.

    The recorder calls this rather than trusting a scope file in a packet directory, because a carry
    posts a verdict with no review behind it, and so rests entirely on this computation."""
    parent, snapshot = PACKET.reviewed_snapshot(head)
    try:
        prior, reusable, why = load_prior(snapshot, prior_path, head)
        slice_entries = sorted(set(entries) | {c["id"][len("entry:"):] for c in (prior or {}).get("claims") or []
                                               if str(c.get("id", "")).startswith("entry:")})
        model, current, facts = engine_state(snapshot, checked(package_maps, snapshot, head, parent), slice_entries)
        result = model.impact(prior if prior is not None else {}, current, ceiling=ceiling_of(facts["policy"], model),
                              reusable=reusable)
        return prior, result, why
    finally:
        PACKET.remove_reviewed_snapshot(parent, snapshot)


def committed_on_branch(snapshot, base):
    """The attestations committed at the snapshot that were recorded on this branch: of commits the
    base does not already hold. What a full review with no --prior would be ignoring."""
    model = scope_model()
    out = []
    for path in sorted((snapshot / model.ATTESTATIONS).glob("*.json")) if (snapshot / model.ATTESTATIONS).is_dir() else []:
        try:
            commit = json.loads(path.read_text(encoding="utf-8")).get("reviewedCommit")
        except (OSError, ValueError):
            continue
        if isinstance(commit, str) and subprocess.run(["git", "merge-base", "--is-ancestor", commit, base],
                                                      cwd=PACKET.ROOT, stdout=subprocess.DEVNULL,
                                                      stderr=subprocess.DEVNULL).returncode != 0:
            out.append(f"{model.ATTESTATIONS}/{path.name}")
    return out


def command_state(args):
    head, parent, snapshot = snapshot_for(args.commit)
    try:
        model, current, _ = engine_state(snapshot, checked(args.package_map, snapshot, head, parent), args.entry)
        current = {k: v for k, v in current.items() if k != "graph"}
        sys.stdout.write(json.dumps({"commit": head, "semanticState": model.state_digest(current), **current},
                                    indent=2, sort_keys=True) + "\n")
    finally:
        PACKET.remove_reviewed_snapshot(parent, snapshot)
    return 0


def command_impact(args):
    head, parent, snapshot = snapshot_for(args.commit)
    try:
        prior, reusable, why = load_prior(snapshot, args.prior, head)
        entries = args.entry or ([c["id"][len("entry:"):] for c in (prior or {}).get("claims") or []
                                  if str(c.get("id", "")).startswith("entry:")])
        model, current, facts = engine_state(snapshot, checked(args.package_map, snapshot, head, parent), entries)
        result = model.impact(prior, current, ceiling=ceiling_of(facts["policy"], model), reusable=reusable)
        if why and result["reasons"]:
            result["reasons"][0]["detail"] += f" ({why})"
        if args.json:
            sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
        else:
            print(describe(result, head))
    finally:
        PACKET.remove_reviewed_snapshot(parent, snapshot)
    return 0


def describe(result, head):
    lines = [f"impact at {head[:12]}: {result['mode'].upper()}"]
    for reason in result["reasons"]:
        lines.append(f"  full review required -- {reason['code']}: {reason['detail']}")
    if result["mode"] != "full":
        lines.append(f"  review {len(result['review'])} claim(s); {len(result['retained'])} retained")
        for claim in result["review"]:
            why = result["invalidated"].get(claim) or (["new"] if claim in result["new"] else ["changed"])
            lines.append(f"    {claim}: {'; '.join(why[:3])}" + (f" (+{len(why) - 3})" if len(why) > 3 else ""))
    if result["mode"] == "none":
        lines.append("  nothing the prior review rested on moved: its evidence stands whole at this head")
    return "\n".join(lines)


def command_delta(args):
    """Write the delta packet for PR `args.pr`, or refuse with the reasons a full review is owed."""
    pull = json.loads(PACKET.gh("pr", "view", str(args.pr), "--json",
                                "number,title,body,headRefOid,baseRefOid,closingIssuesReferences"))
    head = pull.get("headRefOid") or ""
    base = pull.get("baseRefOid") or PACKET.git("rev-parse", "origin/main").strip()
    issues = pull.get("closingIssuesReferences") or []
    if len(issues) != 1:
        raise Refused(f"PR #{args.pr} closes {len(issues)} issues; the rails allow exactly one")
    issue = json.loads(PACKET.gh("issue", "view", str(issues[0]["number"]), "--json", "body"))
    entries = PACKET.entry_ids(issue.get("body"), pull.get("body"))
    out_dir = PACKET.destination(args.out)
    parent, snapshot = PACKET.reviewed_snapshot(head)
    try:
        prior, reusable, why = load_prior(snapshot, args.prior, head)
        copies = checked(args.package_map, snapshot, head, parent)
        model, current, facts = engine_state(snapshot, copies, entries)
        result = model.impact(prior, current, ceiling=ceiling_of(facts["policy"], model), reusable=reusable)
        if result["mode"] == "full":
            reasons = "\n".join(f"  - {r['code']}: {r['detail']}" + (f" ({why})" if why and r["code"] ==
                                                                      "prior-attestation-unusable" else "")
                                for r in result["reasons"])
            raise Refused(f"this change cannot be reviewed as a delta of {args.prior}:\n{reasons}\n"
                          f"A full review answers these. Write its packet with "
                          f"`tools/review-packet.py {args.pr} --role semantic --prior {args.prior} --package-map <path>`.")
        prior_digest = model.attestation_digest(prior)
        stem = f"pr-{args.pr}-{head[:12]}-delta"
        work = parent / "delta-out"
        work.mkdir()
        packets = []
        review_entries = [c[len("entry:"):] for c in result["review"] if c.startswith("entry:")]
        for entry_id in review_entries:
            packet, problem = PACKET.entry_packet(entry_id, work, snapshot, copies)
            if problem:
                raise Refused(f"no entry packet for `{entry_id}`: {problem}")
            packets.append(packet)
        closure_units = sorted({u for claim in result["review"] if claim in current["claims"]
                                for u in current["claims"][claim] if u.startswith("file:")}
                               | {"file:" + c[len("change:"):] for c in result["review"] if c.startswith("change:")})
        closure = {u[len("file:"):]: current["units"].get(u) for u in closure_units}
        prefix = (PACKET.engine_path() + "/") if PACKET.engine_path() else ""
        scoped_paths = sorted(closure) + [f"overlay/{e}.json" for e in review_entries]
        diff = PACKET.git("diff", f"{prior['reviewedCommit']}..{head}", "--", *[prefix + p for p in scoped_paths]) \
            if scoped_paths else ""
        rendered_diff = ("```diff\n" + diff.rstrip() + "\n```") if diff.strip() else ""
        locators = {e: facts["locators"].get(e) for e in review_entries}
        # The locators of the review set's own entries, and of nothing else: the retained claims'
        # citations are not the reviewer's to reread.
        text = model.render_delta_packet(
            prior=prior, prior_digest=prior_digest, head=head, base=base, current=current, impact_record=result,
            entry_packets=[(p["entryId"], p["name"], p["sha256"]) for p in packets], diff=rendered_diff,
            closure_files=closure, locators=locators, tests={e: facts["tests"].get(e) or [] for e in review_entries})
        mode = result["mode"]
        if mode == "none":
            text = (f"# Nothing to review: `{head}`\n\nEvery unit the prior attestation `{prior_digest}` rested on is "
                    f"unchanged at this head. Its evidence stands whole, and a comprehensive PASS is carried with "
                    f"`tools/record-verdict.py --pr {args.pr} --packet <this identity> --reviewer semantic "
                    f"--verdict pass --package-map <path>`, which computes the carry again from the repository "
                    f"before it posts anything.\n")
        measured = model.measure(text, [p["bytes"] for p in packets])
        scope = {
            "scopeFormat": 1, "project": facts["project"], "state": {"units": current["units"],
                                                                     "claims": current["claims"]},
            "impact": result, "maps": facts["maps"], "corpora": facts["corpora"], "charter": facts["charter"],
            "locators": locators,
            "telemetry": {"packetBytes": measured["bytes"], "packetCharacters": measured["characters"],
                          "packetFiles": measured["files"],
                          "changedFiles": len([u for u in result["changedUnits"] if u.startswith("file:")]),
                          "changedEntries": len([u for u in result["changedUnits"] if u.startswith("entry:")]),
                          "closureSize": len(closure), "entriesPresented": len(packets)},
        }
        identity = {
            "reviewPacketFormat": 2, "reviewRole": "semantic", "reviewType": "carry" if mode == "none" else "delta",
            "pullRequest": args.pr, "reviewedCommit": head, "baseCommit": base,
            "reviewPacket": {"path": f"{stem}.md", "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()},
            "reviewContext": delta_context(snapshot, facts, copies),
            "entryPackets": [{"entryId": p["entryId"], "path": p["name"], "sha256": p["sha256"]} for p in packets],
            "prior": {"path": f"{stem}.prior.attestation.json", "sha256": hashlib.sha256(
                (snapshot / args.prior).read_bytes()).hexdigest(), "source": args.prior},
            "scope": {"path": f"{stem}.scope.json"},
        }
        scope_bytes = model.pretty(scope)
        identity["scope"]["sha256"] = hashlib.sha256(scope_bytes).hexdigest()
        after = json.loads(PACKET.gh("pr", "view", str(args.pr), "--json", "headRefOid"))
        if after.get("headRefOid") != head:
            raise Refused(f"PR #{args.pr} moved while its delta packet was being assembled; regenerate")
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{stem}.md").write_text(text, encoding="utf-8")
        for packet in packets:
            (out_dir / packet["name"]).write_bytes(packet["bytes"])
        (out_dir / identity["prior"]["path"]).write_bytes((snapshot / args.prior).read_bytes())
        (out_dir / identity["scope"]["path"]).write_bytes(scope_bytes)
        (out_dir / f"{stem}.review.json").write_bytes(model.pretty(identity))
    finally:
        PACKET.remove_reviewed_snapshot(parent, snapshot)
    print(describe(result, head))
    print(out_dir / f"{stem}.md")
    print(out_dir / f"{stem}.review.json")
    return 0


def delta_context(snapshot, facts, copies):
    """The review context a delta identity carries: the same members a full packet's does (0053)."""
    record_bytes = (snapshot / PROVENANCE).read_bytes()
    policy_bytes = (snapshot / POLICY).read_bytes()
    record = json.loads(record_bytes)
    review = facts["policy"].get("review") or {}
    return {
        "policy": {"path": POLICY, "sha256": hashlib.sha256(policy_bytes).hexdigest(),
                   "semanticContext": review.get("semanticContext"),
                   "independentFallback": review.get("independentFallback") or []},
        "provenance": {"path": PROVENANCE, "sha256": hashlib.sha256(record_bytes).hexdigest()},
        "maps": [{"packageId": p.get("packageId"), "version": p.get("version"), "nupkgSha256": p.get("nupkgSha256", ""),
                  "declaredSha256": next((f.get("sha256") for f in p.get("files") or [] if f.get("role") == "map"), ""),
                  "readSha256": hashlib.sha256(pathlib.Path(c).read_bytes()).hexdigest()}
                 for p, c in zip(PACKET.map_packages(record), copies)],
        "mapsReadFrom": "--package-map, checked against the reviewed commit, and the entry packets built from those exact bytes",
    }


def command_self_review(args):
    head, parent, snapshot = snapshot_for(args.commit)
    try:
        model, current, facts = engine_state(snapshot, checked(args.package_map, snapshot, head, parent), [args.entry])
        digest = model.claim_digest(current, f"entry:{args.entry}")
        path = snapshot / model.SELF_REVIEWS / f"{args.entry}.json"
        if not args.check:
            print(f"# Adversarial self-review for `{args.entry}` at {head[:12]} (claim digest {digest})")
            print(f"# Write it to {model.SELF_REVIEWS}/{args.entry}.json and commit it; docs/adversarial-self-review.md "
                  f"has a question and a test template for each class.")
            for identifier, question in model.SELF_REVIEW_CLASSES:
                print(f"#  {identifier}: {question}")
            sys.stdout.write(model.pretty(model.self_review_skeleton(args.entry, digest)).decode("utf-8"))
            return 0
        record = read_json(path, str(path.relative_to(snapshot))) if path.is_file() else None
        problems = model.self_review_problems(record, args.entry, digest, facts["declaredTests"])
    finally:
        PACKET.remove_reviewed_snapshot(parent, snapshot)
    if problems:
        print("self-review: INCOMPLETE\n" + "\n".join(f"  X  {p}" for p in problems), file=sys.stderr)
        return 1
    print(f"self-review: {args.entry} answers all {len(model.SELF_REVIEW_IDS)} classes at claim digest {digest[:12]}")
    return 0


def command_ruling_review(args):
    """The review of a ruling a `semantic-ruling` owes in place of a self-review (0076).

    Needs no map: a ruling has no entry packet to build. It is bound to the decision record's
    bytes at the commit, so an edit to the ruling after it was reviewed makes the record stale.
    """
    head, parent, snapshot = snapshot_for(args.commit)
    try:
        model = scope_model()
        target = snapshot / args.decision
        data = target.read_bytes() if target.is_file() else b""
        digest = hashlib.sha256(data).hexdigest()
        path = snapshot / model.RULING_REVIEWS / f"{model.ruling_review_stem(args.decision)}.json"
        if not args.check:
            print(f"# Review of the ruling `{args.decision}` at {head[:12]} (record sha256 {digest})")
            print(f"# Write it to {model.RULING_REVIEWS}/{model.ruling_review_stem(args.decision)}.json and commit it; "
                  f"docs/adversarial-self-review.md says what each class asks.")
            for identifier, question in model.RULING_REVIEW_CLASSES:
                print(f"#  {identifier}: {question}")
            sys.stdout.write(model.pretty(model.ruling_review_skeleton(args.decision, digest)).decode("utf-8"))
            return 0
        record = read_json(path, str(path.relative_to(snapshot))) if path.is_file() else None
        problems = model.ruling_review_problems(record, args.decision, digest)
    finally:
        PACKET.remove_reviewed_snapshot(parent, snapshot)
    if problems:
        print("ruling-review: INCOMPLETE\n" + "\n".join(f"  X  {p}" for p in problems), file=sys.stderr)
        return 1
    print(f"ruling-review: {args.decision} answers all {len(model.RULING_REVIEW_IDS)} classes at record "
          f"sha256 {digest[:12]}")
    return 0


def command_verify(args):
    head = PACKET.git("rev-parse", f"{args.commit}^{{commit}}").strip()
    parent, snapshot = PACKET.reviewed_snapshot(head)
    try:
        document, reusable, why = load_prior(snapshot, args.attestation, head)
    finally:
        PACKET.remove_reviewed_snapshot(parent, snapshot)
    if not reusable:
        print(f"verify: NOT REUSABLE -- {why}", file=sys.stderr)
        return 1
    print(f"verify: {args.attestation} is the attestation recorded at {document['reviewedCommit'][:12]} "
          f"({document['reviewType']} {document['result']}, {len(document['claims'])} claims)")
    return 0


def command_telemetry(args):
    model = scope_model()
    paths = args.attestations or sorted(glob.glob(str(ROOT / model.ATTESTATIONS / "*.json")))
    documents = []
    for path in paths:
        document = read_json(path, path)
        problems = model.validate_attestation(document)
        if problems:
            raise Refused(f"{path} is not a valid attestation: {'; '.join(problems[:3])}")
        documents.append(document)
    sys.stdout.write(json.dumps(model.telemetry(documents), indent=2, sort_keys=True) + "\n")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="review-scope.py", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    def maps(p):
        p.add_argument("--package-map", action="append", default=[], metavar="PATH",
                       help="the restored package's corpus-map.json; once per package of a composed engine")

    delta = sub.add_parser("delta", help="write the delta packet for a pull request, or say why a full review is owed")
    delta.add_argument("pr", type=int)
    delta.add_argument("--prior", required=True, help=f"the prior attestation, as committed under reviews/attestations/")
    delta.add_argument("--out")
    maps(delta)
    impact = sub.add_parser("impact", help="what a commit invalidates of a prior attestation")
    impact.add_argument("--prior", required=True)
    impact.add_argument("--commit", default="HEAD")
    impact.add_argument("--entry", action="append", default=[])
    impact.add_argument("--json", action="store_true")
    maps(impact)
    state = sub.add_parser("state", help="the claims and units at a commit")
    state.add_argument("--commit", default="HEAD")
    state.add_argument("--entry", action="append", default=[])
    maps(state)
    self_review = sub.add_parser("self-review", help="the adversarial self-review skeleton for an entry, or --check it")
    self_review.add_argument("entry")
    self_review.add_argument("--commit", default="HEAD")
    self_review.add_argument("--check", action="store_true")
    maps(self_review)
    ruling = sub.add_parser("ruling-review", help="the review skeleton for a decision record a ruling changes, or --check it")
    ruling.add_argument("decision", help="the decision record's engine-relative path, docs/decisions/NNNN-....md")
    ruling.add_argument("--commit", default="HEAD")
    ruling.add_argument("--check", action="store_true")
    verify = sub.add_parser("verify", help="whether a committed attestation is the one recorded")
    verify.add_argument("attestation")
    verify.add_argument("--commit", default="HEAD")
    telemetry = sub.add_parser("telemetry", help="review cost and reuse, from attestations")
    telemetry.add_argument("attestations", nargs="*")
    args = parser.parse_args(argv)
    try:
        return {"delta": command_delta, "impact": command_impact, "state": command_state,
                "self-review": command_self_review, "ruling-review": command_ruling_review,
                "verify": command_verify,
                "telemetry": command_telemetry}[args.command](args)
    except (Refused, PACKET.Refused) as error:
        print(f"review-scope: REFUSED -- {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
