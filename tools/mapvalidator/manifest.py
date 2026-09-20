"""What resolves against the corpus manifest rather than the map: source ids, adapters,
references and the baseline stamp, and each corpus's verification posture and quotation policy
(0013) and whether an engine for it may draw random values (0019).
"""
import os

from .diagnostics import skip, verdict
from mapcontract.entry import (block, corpora_of, entries_of, label, quotes_withheld,
                               reference_identity, references_of)


def check_manifest(ctx):
    """Everything that resolves against the manifest rather than against the map.

    The map's `corpus` and baseline stamp, every `locator.sourceId`, `beyondAdapter.adapter`
    against the adapter declared for that source (0004), and `definedElsewhere.reference`
    against that source's `references` (0005).

    `definedElsewhere` names a corpus that was not admitted, so a reference to a corpus the
    manifest declares, or to a reference marked `admitted: true`, is refused (0026, #115): the
    SRD's Rules Glossary is the same corpus as its combat chapter, and a term defined there is a
    `scope: out` entry the in-scope entry names, not a reference.
    """
    manifest = ctx["manifest"]
    if manifest is None:
        return skip(
            "no manifest was given or found beside the map, so no sourceId, adapter or "
            "reference was resolved. Pass --manifest."
        )
    corpora = {c.get("sourceId"): c for c in manifest.get("corpora") or [] if isinstance(c, dict)}
    if not corpora:
        return skip("the manifest declares no corpora, so nothing could be resolved against it")

    doc, bad, checked = ctx["map"], [], 0

    # 0047: the Phase-1 `references` list is historical evidence. Mapping-time discoveries are
    # additive only, live in `referenceAmendments`, and may not admit a corpus or mutate any
    # baseline/licensing fact because the amendment shape has nowhere to put those fields.
    for source_id, corpus in corpora.items():
        amendments = corpus.get("referenceAmendments")
        if amendments is None:
            continue
        checked += 1
        if not isinstance(amendments, list) or not amendments:
            bad.append(f"  X  manifest {source_id}: `referenceAmendments` is a non-empty list")
            continue
        historical = {r.get("sourceId") for r in corpus.get("references") or []
                      if isinstance(r, dict)}
        amended = set()
        for at, amendment in enumerate(amendments, start=1):
            where = f"manifest {source_id}: referenceAmendments[{at}]"
            if not isinstance(amendment, dict):
                bad.append(f"  X  {where} is not an object")
                continue
            extra = sorted(set(amendment) - {"discoveredDuring", "decision", "references"})
            if extra:
                bad.append(f"  X  {where}: amendment may only record discoveredDuring, decision "
                           f"and references; got {', '.join(extra)}")
            if amendment.get("discoveredDuring") != "mapping":
                bad.append(f"  X  {where}: discoveredDuring must be 'mapping'")
            decision = amendment.get("decision")
            if not isinstance(decision, str) or not decision:
                bad.append(f"  X  {where}: decision names the record authorising the correction")
            refs = amendment.get("references")
            if not isinstance(refs, list) or not refs:
                bad.append(f"  X  {where}: references is a non-empty list")
                continue
            for pos, reference in enumerate(refs, start=1):
                item = f"{where}.references[{pos}]"
                if not isinstance(reference, dict) or set(reference) != {"sourceId", "citation", "admitted"}:
                    bad.append(f"  X  {item}: a correction reference has exactly sourceId, citation "
                               f"and admitted")
                    continue
                target, citation = reference.get("sourceId"), reference.get("citation")
                if not isinstance(target, str) or not target:
                    bad.append(f"  X  {item}: sourceId is a non-empty string")
                if not isinstance(citation, str) or not citation.strip():
                    bad.append(f"  X  {item}: citation is a non-empty string")
                elif reference_identity(reference) is None:
                    bad.append(f"  X  {item}: citation {citation!r} does not match sourceId "
                               f"{target!r} as one reference boundary")
                if reference.get("admitted") is not False:
                    bad.append(f"  X  {item}: a boundary correction is referenced-but-not-admitted; "
                               f"admission is a separate Phase-1 act")
                if target in corpora:
                    bad.append(f"  X  {item}: {target!r} is already admitted; a mapping-time "
                               f"boundary amendment cannot retroactively admit or reclassify it")
                if target in historical or target in amended:
                    bad.append(f"  X  {item}: {target!r} is already declared; an amendment records "
                               f"a newly discovered boundary, not a rewrite")
                if isinstance(target, str) and target:
                    amended.add(target)
    corpus_id = doc.get("corpus")
    declared = corpora.get(corpus_id)
    if declared is None:
        bad.append(f"  X  map: corpus {corpus_id!r} is not declared in the manifest")
    else:
        checked += 1
        baseline = doc.get("baseline") if isinstance(doc.get("baseline"), dict) else {}
        for field in ("contentHash", "hashDerivation"):
            if baseline.get(field) and declared.get(field) and baseline[field] != declared[field]:
                bad.append(
                    f"  X  map: baseline {field} {baseline[field]!r} does not match the manifest's "
                    f"{declared[field]!r} for {corpus_id}"
                )

    for position, entry in enumerate(entries_of(doc)):
        if not isinstance(entry, dict):
            continue
        name = label(entry, position)
        source_id = block(entry, "locator").get("sourceId")
        source = corpora.get(source_id)
        if source_id is not None:
            checked += 1
            if source is None:
                bad.append(f"  X  {name}: locator.sourceId {source_id!r} is not declared in the manifest")
        if "beyondAdapter" in entry:
            checked += 1
            adapter = block(entry, "beyondAdapter").get("adapter")
            if source is None:
                bad.append(f"  X  {name}: beyondAdapter names adapter {adapter!r}, but its source is not in the manifest")
            elif adapter != source.get("adapter"):
                bad.append(
                    f"  X  {name}: beyondAdapter.adapter is {adapter!r}, but {source_id} declares "
                    f"{source.get('adapter')!r}"
                )
        if "definedElsewhere" in entry:
            checked += 1
            reference = block(entry, "definedElsewhere").get("reference")
            declared_references = references_of(source)
            known = {r.get("sourceId") for r in declared_references}
            admitted = reference in corpora or any(
                r.get("sourceId") == reference and r.get("admitted") is True for r in declared_references)
            if source is None:
                bad.append(f"  X  {name}: definedElsewhere names {reference!r}, but its source is not in the manifest")
            elif admitted:
                bad.append(
                    f"  X  {name}: definedElsewhere names {reference!r}, a corpus that was admitted; it "
                    f"answers only a corpus that was not. A meaning the same corpus gives outside the "
                    f"slice is a `scope: out` entry quoting that passage, named by this entry's "
                    f"`crossReferences` (and `dependsOn`, where it modifies the rule) (0026, #115)"
                )
            elif reference not in known:
                bad.append(
                    f"  X  {name}: definedElsewhere.reference {reference!r} is not in {source_id}'s "
                    f"`references`; an elsewhere-defined *input* is kind: assertion, not this field"
                )
    if not checked:
        return skip("no entry carried anything that resolves against the manifest")
    return verdict(bad, f"{checked} manifest resolutions all succeed", "something does not resolve in the manifest")


VERIFICATION_POSTURES = {"committed-copy", "local-copy"}
QUOTATION_POLICIES = {"verbatim", "withheld"}
RANDOMNESS = {"none", "seeded"}


def check_postures(ctx):
    """How each corpus is verified, and whether a map may quote it, are declared per corpus (0013).

    0002 made *where a corpus lives* a property of its licence. 0013 carries that one step on:
    *how a consumer verifies the baseline* is declared per corpus too, and so is *whether the
    map may carry verbatim spans of it* -- because since #18 a map quotes a few hundred sentences
    of its corpus, and for a corpus that may not be committed the map is itself the
    redistribution question.

    Every admitted corpus in the manifest declares all three:

      * `verification`: `committed-copy` (the bytes are in this repository, at `committedPath`,
        so anyone -- CI included -- can verify the hash) or `local-copy` (they are not; a holder
        of a legal copy points `envVar` at it, and everyone else is told NOT VERIFIED, never ok);
      * `quotation`: `verbatim` (entries quote spans, as corpus-map.md requires) or `withheld`
        (the licence forbids it, so no entry citing the corpus carries `evidence`);
      * `randomness` (0019): `none` (a conforming engine draws no random value, so it may not
        reach RulesKernel.Randomness) or `seeded` (the rules call for chance, and every draw goes
        through the kernel's seeded, replayable source).

    And what follows from them:

      * `never-commit` is `local-copy`: bytes the repository may not hold cannot be verified
        from it;
      * `local-copy` names `envVar`, or nobody could ever verify it;
      * `committed-copy` names `committedPath`, and the file exists beside the manifest;
      * under `withheld`, an entry that quotes anyway fails.

    What it cannot do: hash anything. `hashDerivation` names what a digest covers and this file
    does not know how to recompute any derivation, so a committed file with the wrong bytes
    passes here. Reporting the posture and verifying the hash is the gate's job. Nor does it
    decide a licence: `quotation` is declared by a person, and 0013 is explicit that nothing
    infers it.
    """
    manifest = ctx["manifest"]
    corpora = corpora_of(manifest)
    if not corpora:
        return skip("no manifest, or a manifest declaring no corpora, so no corpus's verification "
                    "posture, quotation policy or randomness was read. Pass --manifest.")
    base = os.path.dirname(os.path.abspath(ctx["manifest_path"])) if ctx.get("manifest_path") else None
    bad = []
    for source_id, corpus in corpora.items():
        name = f"manifest {source_id}"
        posture, quotation = corpus.get("verification"), corpus.get("quotation")
        if posture not in VERIFICATION_POSTURES:
            bad.append(f"  X  {name}: verification is {posture!r}, outside "
                       f"{{{', '.join(sorted(VERIFICATION_POSTURES))}}}; a corpus with no declared "
                       f"posture is a failure, not a default (0002, 0013)")
        if quotation not in QUOTATION_POLICIES:
            bad.append(f"  X  {name}: quotation is {quotation!r}, outside "
                       f"{{{', '.join(sorted(QUOTATION_POLICIES))}}}; whether a map may quote its "
                       f"corpus is declared per corpus, never assumed")
        if corpus.get("randomness") not in RANDOMNESS:
            bad.append(f"  X  {name}: randomness is {corpus.get('randomness')!r}, outside "
                       f"{{{', '.join(sorted(RANDOMNESS))}}}; whether an engine may draw random values "
                       f"is declared per corpus, never assumed (0019)")
        if corpus.get("boundaryPolicy") == "never-commit" and posture == "committed-copy":
            bad.append(f"  X  {name}: is `never-commit` but claims `committed-copy`; bytes the "
                       f"repository may not hold cannot be verified from it")
        if posture == "local-copy" and not (isinstance(corpus.get("envVar"), str) and corpus["envVar"].strip()):
            bad.append(f"  X  {name}: is `local-copy` and names no `envVar`, so nobody holding a "
                       f"legal copy has anywhere to point the verifier")
        if posture == "committed-copy":
            path = corpus.get("committedPath")
            if not isinstance(path, str) or not path.strip():
                bad.append(f"  X  {name}: is `committed-copy` and names no `committedPath`")
            elif base is None or not os.path.isfile(os.path.join(base, path)):
                bad.append(f"  X  {name}: committedPath {path!r} is not a file beside the manifest; "
                           f"a committed copy that is not committed is `local-copy`")

    for position, entry in enumerate(entries_of(ctx["map"])):
        if not isinstance(entry, dict):
            continue
        if quotes_withheld(ctx.get("manifest"), entry):
            if entry.get("evidence"):
                bad.append(f"  X  {label(entry, position)}: quotes `evidence` from "
                           f"{block(entry, 'locator').get('sourceId')}, whose quotation is `withheld`; "
                           f"the span is recorded as absent, never quoted and never summarised")
    postures = sorted(f"{s}: {c.get('verification')}, {c.get('quotation')}, randomness {c.get('randomness')}"
                      for s, c in corpora.items())
    return verdict(bad, f"{len(corpora)} corpus postures declared ({'; '.join(postures)})",
                   "a corpus's verification posture, quotation policy or randomness is missing or contradicted")
