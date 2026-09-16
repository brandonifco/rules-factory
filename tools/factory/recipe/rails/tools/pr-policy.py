#!/usr/bin/env python3
"""The pull request contract, checked mechanically.

    tools/pr-policy.py <pr-number>

Emitted by rules-factory as a managed file (decision 0029), and run by
`.github/workflows/pr-policy.yml` on every open, edit, push and reopen.

**What this is for.** A pull request is where a change stops being the implementer's and becomes
the repository's, and the only thing a reader six months later has is what it said. A vague pull
request is not a formatting problem: it is a change whose behavioural claim nobody stated, whose
evidence nobody can re-run, and whose scope nobody bounded -- and each of those is how a defect
gets merged with everyone's agreement.

So this checks what can be checked mechanically, and nothing it cannot:

  1. exactly one real `Closes #<n>` -- one branch closes one issue;
  2. every mandatory section is present and filled, not left as its placeholder;
  3. the evidence section shows a command and its output, not a claim that it passed;
  4. a change touching the semantic surface names an entry and a locator;
  5. agent provenance says who implemented and who reviewed;
  6. the linked issue carries exactly one risk label and exactly one state label.

**What it cannot check, and does not pretend to.** Whether the behavioural claim is true, whether
the evidence was really run, whether the mutation was really observed to fail, or whether the
named reviewer really reviewed. Those are a reviewer's, and the review verdict recorded against
the head commit is where they land (`tools/record-verdict.py`). A policy check that implied
otherwise would make the pull request look more verified than it is.

Label strings and the semantic surface come from `.github/agent-policy.json`, which the engine
owns. Standard library only, plus `gh` (or `$RULES_ENGINE_GH`).
"""
import argparse
import json
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
POLICY = ".github/agent-policy.json"

# The template's headings, and what each is for. A pull request is judged against these names, so
# the template and this list move together (both are managed rails, emitted by the same factory).
SECTIONS = (
    ("Linked issue", "which issue this closes"),
    ("Exact behavioural claim", "what the engine does now that it did not do before"),
    ("Scope, and what this deliberately does not do", "what makes the diff reviewable"),
    ("Map and rules conformance", "the entry, the map version and the locator"),
    ("Tests and evidence", "the commands, and what they printed"),
    ("Determinism", "what this change does about anything that reads the machine"),
    ("Decisions and trade-offs", "what you chose and what you rejected"),
    ("Known limitations and unresolved behaviour", "what this does not answer"),
    ("Agent provenance", "who implemented, and who reviewed"),
    ("Unrelated changes", "there are none, or they are named"),
)
CLOSES = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)\b", re.I)
FENCE = re.compile(r"```.*?```", re.S)
# "tests pass", "all green", "CI is happy": a claim in the place the template asks for output.
CLAIM_NOT_EVIDENCE = re.compile(r"^\s*(?:all\s+)?(?:tests?|checks?|ci|gate|validate(?:\.sh)?)\s+"
                                r"(?:pass(?:es|ed|ing)?|are\s+green|is\s+green|green|ok)\s*\.?\s*$", re.I | re.M)


class Failed(Exception):
    """A finding a person has to act on. Every one names what to do."""


def gh(*args):
    command = [os.environ.get("RULES_ENGINE_GH", "gh"), *args]
    done = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=ROOT, timeout=120)
    if done.returncode != 0:
        raise Failed(f"{' '.join(command)} failed: {done.stderr.strip() or done.stdout.strip()}")
    return done.stdout


def policy():
    with open(ROOT / POLICY, encoding="utf-8") as handle:
        return json.load(handle)


def is_semantic(path, patterns):
    """Whether `path` is on the semantic surface. `**` spans directories; `*` does not."""
    for pattern in patterns:
        regex = re.escape(pattern).replace(r"\*\*/", "(?:.*/)?").replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
        if re.fullmatch(regex, path):
            return True
    return False


def sections(body):
    """The body split into `## Heading` -> text, with HTML comments removed.

    The template's guidance lives in comments, so a section that still holds only its comment is
    empty here -- which is the point: a section is filled when somebody wrote in it.
    """
    without_comments = re.sub(r"<!--.*?-->", "", body or "", flags=re.S)
    found = {}
    current = None
    for line in without_comments.splitlines():
        heading = re.match(r"^##\s+(.*?)\s*$", line)
        if heading:
            current = heading.group(1)
            found[current] = []
        elif current is not None:
            found[current].append(line)
    return {name: "\n".join(lines).strip() for name, lines in found.items()}


def check_closes(body, findings):
    """Exactly one `Closes #n`, outside code fences: one branch, one issue, one pull request."""
    prose = FENCE.sub("", re.sub(r"<!--.*?-->", "", body or "", flags=re.S))
    numbers = sorted({number for _, number in ((m.group(0), m.group(1)) for m in CLOSES.finditer(prose))})
    if not numbers:
        findings.append("no `Closes #<n>`: a pull request closes exactly one issue, and says which "
                        "(AGENTS.md section 4). Add it to the Linked issue section.")
    elif len(numbers) > 1:
        findings.append(f"this closes {len(numbers)} issues (#{', #'.join(numbers)}): split it, so that each "
                        f"change can be reviewed, reverted and explained on its own.")
    return numbers[0] if len(numbers) == 1 else None


# The one section a change may honestly answer "N/A": nothing it touches is on the rules surface.
# Whether that is true is not taken on the author's word -- check_conformance decides it from the
# files the pull request actually changes.
MAY_BE_NA = "Map and rules conformance"


def check_sections(body, findings):
    present = sections(body)
    filled = {}
    for name, purpose in SECTIONS:
        empty = {"", "-", "TODO"} if name == MAY_BE_NA else {"", "-", "N/A", "TODO"}
        if name not in present:
            findings.append(f"the section `## {name}` is missing ({purpose}). The template is "
                            f".github/pull_request_template.md.")
        elif present[name] in empty:
            findings.append(f"`## {name}` is empty ({purpose}).")
        else:
            filled[name] = present[name]
    return filled


def check_evidence(filled, findings):
    evidence = filled.get("Tests and evidence")
    if evidence is None:
        return
    fences = FENCE.findall(evidence)
    body = "\n".join(fences)
    if not fences:
        findings.append("`## Tests and evidence` shows no command and no output. Paste what you ran and what it "
                        "printed: a claim is not evidence, and a reviewer cannot re-run a summary.")
    elif not re.search(r"(?m)^\s*(?:\$\s*)?\S*(?:validate\.sh|dotnet|python3|pytest)\b", body):
        findings.append("`## Tests and evidence` shows no command that was run. The gate is "
                        "`./scripts/validate.sh full`; show it, and what it printed.")
    if CLAIM_NOT_EVIDENCE.search(evidence) and len(body.strip().splitlines()) < 3:
        findings.append("`## Tests and evidence` says the tests pass rather than showing them passing. "
                        "This repository has twice shipped a check that counted work it had not done.")
    # Asked whatever the fences hold: the mutation obligation is about the tests, not the formatting.
    if "mutation" not in evidence.lower():
        findings.append("`## Tests and evidence` names no mutation. Every test records the mutation that makes it "
                        "fail, and you must have watched it fail -- a test nobody has watched fail is not yet a test.")


def check_conformance(filled, semantic_files, findings):
    conformance = filled.get("Map and rules conformance")
    if conformance is None or not semantic_files:
        return
    if re.fullmatch(r"(?i)\s*n/?a\.?\s*", conformance):
        findings.append(f"`## Map and rules conformance` says N/A, but this change touches the semantic surface "
                        f"({', '.join(sorted(semantic_files)[:3])}...). Name the entry id, the map version and the "
                        f"locator: an implementation of an unnamed rule cannot be reviewed against one.")
        return
    for field, what in (("entry", "the entry id, which is what ties this to the map"),
                        ("map", "the map package and version this was implemented against"),
                        ("locator", "the locator, which is where the rule is")):
        # The template's bullets read "entry id(s):", "map package and version:", "source
        # locator(s):" -- so the word is looked for anywhere in the label, not at its start.
        if not re.search(rf"(?im)^[^\n:]*\b{field}[^:\n]*:[ \t]*\S", conformance):
            findings.append(f"`## Map and rules conformance` does not name {what}.")


def check_provenance(filled, findings):
    provenance = filled.get("Agent provenance")
    if provenance is None:
        return
    for field in ("implemented by", "structurally reviewed by", "semantically reviewed by"):
        if not re.search(rf"(?im)^[^\n:]*\b{re.escape(field)}[ \t]*:[ \t]*\S", provenance):
            findings.append(f"`## Agent provenance` does not say who this was {field.replace(' by', '')} by. "
                            f"A merged commit must say who did what without opening a transcript.")


def check_issue_labels(number, settings, findings):
    issue = json.loads(gh("issue", "view", str(number), "--json", "number,state,labels"))
    names = {label["name"] for label in issue.get("labels") or []}
    labels = settings.get("labels") or {}
    risks = names & {labels.get("normalRisk"), labels.get("independentRisk")}
    states = names & {labels.get("ready"), labels.get("blocked"), labels.get("needsDecision")}
    if len(risks) != 1:
        findings.append(f"issue #{number} carries {len(risks)} risk labels ({', '.join(sorted(risks)) or 'none'}); "
                        f"exactly one is required, because it decides whether an independent verdict is needed.")
    if len(states) != 1:
        findings.append(f"issue #{number} carries {len(states)} state labels ({', '.join(sorted(states)) or 'none'}); "
                        f"exactly one is required.")
    if labels.get("needsDecision") in names:
        findings.append(f"issue #{number} is {labels['needsDecision']}: the question it raises is not answered, and "
                        f"an implementation cannot answer it for itself (AGENTS.md section 6).")
    return issue


def main(argv=None):
    parser = argparse.ArgumentParser(prog="pr-policy.py", description=__doc__.split("\n")[0])
    parser.add_argument("pr", type=int, help="the pull request number")
    args = parser.parse_args(argv)

    findings = []
    try:
        settings = policy()
        pull = json.loads(gh("pr", "view", str(args.pr), "--json", "number,title,body,files"))
        body = pull.get("body") or ""
        changed = [f["path"] for f in pull.get("files") or []]
        semantic_files = {path for path in changed
                          if is_semantic(path, (settings.get("review") or {}).get("semanticPaths") or [])}

        linked = check_closes(body, findings)
        filled = check_sections(body, findings)
        check_evidence(filled, findings)
        check_conformance(filled, semantic_files, findings)
        check_provenance(filled, findings)
        if linked is not None:
            check_issue_labels(linked, settings, findings)
    except Failed as error:
        print(f"pr-policy: cannot check PR #{args.pr} -- {error}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as error:
        print(f"pr-policy: cannot check PR #{args.pr} -- {error}", file=sys.stderr)
        return 2

    if findings:
        print(f"pr-policy: PR #{args.pr} does not satisfy the contract ({len(findings)} finding(s)):\n")
        for finding in findings:
            print(f"  X  {finding}\n")
        print("The contract is .github/pull_request_template.md and AGENTS.md. None of this is about form: each "
              "line above is something a reviewer would otherwise have to take on trust.")
        return 1
    print(f"pr-policy: PR #{args.pr} satisfies the contract "
          f"({len(SECTIONS)} sections, one linked issue, evidence and provenance present).")
    print("What this does not say: that the claim is true, that the evidence was run, or that the named reviewers "
          "reviewed. Those are the review verdict's, recorded against the head commit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
