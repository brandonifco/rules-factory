#!/usr/bin/env python3
"""onboard -- a repository has a verified route to the authorized KVM runners, or it says why not.

The owner's directive is that every authorized CI run executes on the KVM runners (`factory-ci-1`
at home, `factory-ci-2` at the office); GitHub schedules and reports jobs, and a GitHub-hosted
runner is never a fallback. Nothing used to check that a repository could reach one: a private
repository whose workflows carried the runner line and whose variable was set sat queued for a day
because no runner was registered for it. Two commands close that:

  onboard.py check OWNER/REPO [--json FILE]   read-only, GitHub only (factory-ci onboard-check).
      Writes the record, prints one line per finding and the verdict. Exit 0 pass, 1 findings,
      2 something could not be read (never a pass).
  onboard.py onboard OWNER/REPO               private repositories only (factory-ci onboard). Idempotent:
      registers this host's runner unless this guest already holds a correct, online registration,
      refuses to replace a same-named runner this guest does not hold, sets FACTORY_RUNS_ON unless it
      is exact, and then runs the check. A public repository is refused: it never has a standing
      registration (decision 0080); `trust` and `enable` serve it by dispatch.
  onboard.py guard OWNER/REPO                 the replacement check alone, run by `factory-ci register`.

`verify` is what `factory rails --check` calls for its "Self-hosted CI route" row. It reads
GitHub through any object with `get(path)`, so the rails read through `gh` and the host through
`dispatch.GitHub`. The list of authorized runners is `runners.json`, a reviewed file; so is its list of
the jobs that deliberately stay on a GitHub-hosted runner (decision 0080 point 8: publication
credentials, manual maintenance), each named by repository, workflow, job and exact `runs-on`. Such a job
is reported as deliberately hosted, not as a finding, only in a public repository and only while it is
exactly as listed.
Standard library only.
"""
import base64
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
from datetime import datetime, timezone

sys.dont_write_bytecode = True
KIT = os.path.dirname(os.path.abspath(__file__))
RUNNERS = os.path.join(KIT, "runners.json")
SCHEMA = "factory-ci/onboarding/1"
RUNS_ON_VARIABLE = "FACTORY_RUNS_ON"
TRUSTED_VARIABLE = "FACTORY_RUNS_ON_TRUSTED"
#: tools/factory/repository.py's RUNS_ON_LINE, which every recipe carries as its only `runs-on`; a test
#: holds this copy to the original.
RUNS_ON_LINE = ("    runs-on: ${{ fromJSON(github.actor == github.repository_owner && github.triggering_actor == "
                "github.repository_owner && (github.event.pull_request.head.repo.full_name || "
                "!github.event.pull_request && github.repository) == github.repository && vars.FACTORY_RUNS_ON_TRUSTED "
                "|| vars.FACTORY_RUNS_ON || '\"ubuntu-24.04\"') }}")


def _load(name):
    """A sibling module of the kit, by path: the kit runs under `python3 -I`, with no script directory
    on the path. One copy per process, whoever asks."""
    key = f"_factory_ci_{name}"
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, os.path.join(KIT, f"{name}.py"))
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
    return sys.modules[key]


dispatch = _load("dispatch")
LABELS = dispatch.LABELS


class OnboardError(Exception):
    """Something this program will not do, or could not do. Nothing is reported as passed."""


class Unreadable(OnboardError):
    """A GitHub read failed: the check has no verdict, and says what it could not read."""


class Failed(OnboardError):
    """A write, the guest, or the login failed, naming what was missing."""


class Refused(OnboardError):
    """A request this program refuses by design (a public repository; another host's runner)."""


# ------------------------------------------------------------------------------------ the list --

def load_runners(path=RUNNERS):
    with open(path, encoding="utf-8") as handle:
        document = json.load(handle)
    return document["runners"]


def authorized_names():
    return [entry["name"] for entry in load_runners()]


def load_hosted_jobs(path=RUNNERS):
    """The reviewed list of jobs that stay on a hosted runner on purpose: [{repository, workflow, job,
    runs_on, reason}]. No list is no job."""
    with open(path, encoding="utf-8") as handle:
        return json.load(handle).get("hosted_jobs", [])


def is_jit(name):
    return re.fullmatch(r".+-jit-[0-9a-f]+", name or "") is not None


def is_authorized(name, names=None):
    """A listed runner VM, or its one-job runner `<name>-jit-<hex>` (dispatch.py starts those)."""
    return any(name == listed or re.fullmatch(re.escape(listed) + r"-jit-[0-9a-f]+", name or "")
               for listed in (names if names is not None else authorized_names()))


def label_names(labels):
    return [str(label.get("name") if isinstance(label, dict) else label) for label in labels or []]


def exact(labels):
    """Whether these are exactly factory-ci's labels, as GitHub compares them: ignoring case."""
    return sorted(label.casefold() for label in label_names(labels)) == sorted(label.casefold() for label in LABELS)


def name_of(repository):
    """The guest's name for a repository's account (`factory-ci`'s name_of)."""
    return re.sub(r"[^a-z0-9-]", "-", repository.split("/", 1)[1].lower())


def check_repository(repository):
    if not dispatch.REPOSITORY.fullmatch(repository or ""):
        raise Failed(f"give OWNER/REPO, not {repository!r}")


# -------------------------------------------------------------------------------- reading GitHub --

#: What GitHub's answer to each kind of call means for the credential, so a refusal names the
#: permission that is missing instead of an HTTP code.
PERMISSIONS = (
    (re.compile(r"/actions/runners/registration-token$"), "Administration: write (repository admin)"),
    (re.compile(r"/actions/runners"), "Administration: read (repository admin)"),
    (re.compile(r"/actions/variables"), "Variables: read and write (repository admin)"),
    (re.compile(r"/contents/"), "Contents: read"),
    (re.compile(r"^/repos/[^/]+/[^/]+$"), "Metadata: read"),
)


def permission(path):
    bare = path.split("?", 1)[0]
    return next((need for pattern, need in PERMISSIONS if pattern.search(bare)), "read access")


def describe(error):
    code = getattr(error, "code", None)
    return f"HTTP {code} {getattr(error, 'reason', '')}".strip() if code else f"{type(error).__name__}: {error}"


def read(github, what, path, missing_ok=False):
    """`github.get(path)`, or Unreadable naming `what` and the permission it needs."""
    try:
        return github.get(path)
    except AssertionError:
        raise
    except urllib.error.HTTPError as error:
        if error.code == 404 and missing_ok:
            return None
        raise Unreadable(f"could not read {what} ({path.split('?', 1)[0]}): {describe(error)}; "
                         f"the credential needs {permission(path)}") from error
    except Exception as error:  # a network error, a bad document: no verdict either way
        raise Unreadable(f"could not read {what} ({path.split('?', 1)[0]}): {describe(error)}; "
                         f"the credential needs {permission(path)}") from error


def pages(github, what, path, key, size=100, limit=10):
    """Every item of a paginated list. A list GitHub cut short is not a list: it is Unreadable."""
    items, separator = [], "&" if "?" in path else "?"
    for page in range(1, limit + 1):
        chunk = read(github, what, f"{path}{separator}per_page={size}&page={page}")
        batch = chunk.get(key) if isinstance(chunk, dict) else chunk
        if not isinstance(batch, list):
            raise Unreadable(f"could not read {what} ({path}): GitHub's answer has no {key} list")
        items.extend(batch)
        if len(batch) < size:
            return items
    raise Unreadable(f"could not read {what} ({path}) whole: more than {limit * size} {key}")


def write(github, what, method, path, body=None):
    try:
        return github.call(method, path, body)
    except Exception as error:
        raise Failed(f"could not {what} ({method} {path}): {describe(error)}; "
                     f"the credential needs {permission(path)}") from error


class GhApi:
    """Reads through the `gh` CLI, for callers that have `gh` and not the host's token: the same `get`
    as `dispatch.GitHub`, and nothing that writes. A failure is an HTTPError carrying gh's status."""

    def __init__(self, gh="gh"):
        self.gh = gh

    def get(self, path, cache=False):
        done = subprocess.run([self.gh, "api", path.lstrip("/")], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, timeout=120)
        if done.returncode != 0:
            message = (done.stderr or done.stdout).strip() or "gh api failed"
            found = re.search(r"HTTP (\d{3})", message)
            code = int(found.group(1)) if found else (404 if "Not Found" in message else None)
            if code:
                raise urllib.error.HTTPError(path, code, message, {}, None)
            raise RuntimeError(message)
        return json.loads(done.stdout or "null")


# ------------------------------------------------------------------------------------ workflows --

JOB_KEY = re.compile(r"""(?:"([^"]+)"|'([^']+)'|([^\s:#'"{}\[\]]+))\s*:\s*(?:#.*)?$""")


def jobs_of(text):
    """[{job, runs_on, uses}] for each job under a workflow file's top-level `jobs:`.

    Read line by line: the shape that matters is fixed (a job's own `runs-on` is its first-level
    key), and nothing here may need a YAML library. A job written in a form it cannot read is
    returned with `runs_on` None and `unreadable` set, so it fails rather than passes."""
    found, in_jobs, job_indent, child_indent, current = [], False, None, None, None
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent == 0:
            in_jobs, current, job_indent = bool(re.match(r"jobs:\s*(#.*)?$", line)), None, None
            continue
        if not in_jobs:
            continue
        if job_indent is None:
            job_indent = indent
        if indent == job_indent:
            key = JOB_KEY.match(stripped)
            current = {"job": next((g for g in key.groups() if g), None) if key else stripped,
                       "runs_on": None, "uses": None, "line": None, "unreadable": key is None}
            child_indent = None
            found.append(current)
            continue
        if current is None or indent < job_indent:
            continue
        if child_indent is None:
            child_indent = indent
        if indent == child_indent:
            keyed = re.match(r"(runs-on|uses)\s*:\s*(.*)$", stripped)
            if keyed and keyed.group(1) == "runs-on":
                current["runs_on"], current["line"] = keyed.group(2).strip(), stripped
            elif keyed:
                current["uses"] = keyed.group(2).strip()
    return found


def scan_workflows(github, repository, branch):
    """[{path, job, runs_on, ok}] for every job of every workflow file on the default branch, and the
    paths read. ok is True (the contract line), False, or None (a reusable-workflow job with no
    `runs-on` of its own: reported, not failed). No workflow directory is no entries."""
    ref = urllib.parse.quote(branch, safe="")
    listing = read(github, "the workflow directory", f"/repos/{repository}/contents/.github/workflows?ref={ref}", missing_ok=True)
    if listing is None:
        return [], []
    if not isinstance(listing, list):
        raise Unreadable(f"could not read the workflow directory (/repos/{repository}/contents/.github/workflows): not a directory listing")
    paths = sorted(item["path"] for item in listing
                   if isinstance(item, dict) and item.get("type") == "file" and re.search(r"\.ya?ml$", item.get("path", "")))
    entries = []
    for path in paths:
        document = read(github, f"workflow {path}", f"/repos/{repository}/contents/{urllib.parse.quote(path)}?ref={ref}")
        if not isinstance(document, dict) or document.get("encoding") != "base64":
            raise Unreadable(f"could not read workflow {path}: GitHub did not return its content")
        try:
            text = base64.b64decode(document.get("content") or "").decode("utf-8")
        except ValueError as error:
            raise Unreadable(f"could not read workflow {path}: {error}") from error
        jobs = jobs_of(text)
        for job in jobs:
            if job["runs_on"] is not None or job["line"] is not None:
                ok = job["line"] == RUNS_ON_LINE.strip()
            else:
                ok = None if job["uses"] and not job["unreadable"] else False
            entries.append({"path": path, "job": job["job"], "runs_on": job["runs_on"], "ok": ok,
                            **({"uses": job["uses"]} if job["uses"] else {})})
        if not jobs:
            entries.append({"path": path, "job": None, "runs_on": None, "ok": False})
    return entries, paths


# -------------------------------------------------------------------------------------- verify --

def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def variable_value(variables, name):
    """(set?, the labels it holds or None when it is not a JSON list of strings)."""
    if name not in variables:
        return False, None
    try:
        value = json.loads(variables[name])
    except (TypeError, ValueError):
        return True, None
    return True, value if isinstance(value, list) and all(isinstance(v, str) for v in value) else None


def verify(repository, github, now=None, hosted_jobs=None):
    """The onboarding record for `repository`: read-only, GitHub only. See the module's note.
    `hosted_jobs` is runners.json's list of deliberately hosted jobs unless a caller gives another.

    Raises Unreadable when anything it needs could not be read: there is no verdict then."""
    check_repository(repository)
    repo = read(github, "the repository", f"/repos/{repository}")
    private = (repo or {}).get("private")
    if not isinstance(private, bool):
        raise Unreadable(f"could not read the repository (/repos/{repository}): GitHub did not say whether it is private")
    branch = repo.get("default_branch")
    if not branch:
        raise Unreadable(f"could not read the repository (/repos/{repository}): no default branch")
    visibility = repo.get("visibility") or ("private" if private else "public")
    runners = pages(github, "the repository's runners", f"/repos/{repository}/actions/runners", "runners")
    variables = {item.get("name"): item.get("value") for item in
                 pages(github, "the repository's variables", f"/repos/{repository}/actions/variables", "variables", size=30)}
    workflows, paths = scan_workflows(github, repository, branch)

    names, findings = authorized_names(), []
    listed = []
    for runner in sorted(runners, key=lambda r: str(r.get("name"))):
        name = str(runner.get("name"))
        entry = {"name": name, "status": runner.get("status"), "busy": bool(runner.get("busy")),
                 "labels": label_names(runner.get("labels")), "authorized": is_authorized(name, names)}
        listed.append(entry)
        if not entry["authorized"]:
            findings.append(f"runner {name} is not an authorized factory-ci runner (tools/ci-runner/runners.json lists "
                            f"{', '.join(names)}): it could take this repository's jobs")
        if not exact(entry["labels"]):
            findings.append(f"runner {name} has labels {', '.join(entry['labels']) or 'none'}, not exactly "
                            f"{', '.join(LABELS)}")
    standing = [r for r in listed if not is_jit(r["name"])]
    seen, trusted_seen = variable_value(variables, RUNS_ON_VARIABLE), variable_value(variables, TRUSTED_VARIABLE)
    if private:
        if not any(r["authorized"] and r["status"] == "online" and exact(r["labels"]) for r in standing):
            findings.append("no authorized runner is online with exactly factory-ci's labels: a job would queue until "
                            f"one is (`factory-ci onboard {repository}` on the KVM host)")
        if not seen[0]:
            findings.append(f"{RUNS_ON_VARIABLE} is not set: the repository's jobs ask for a hosted runner "
                            f"(`factory-ci onboard {repository}` sets it)")
        elif not (seen[1] is not None and exact(seen[1])):
            findings.append(f"{RUNS_ON_VARIABLE} is {variables[RUNS_ON_VARIABLE]!r}, not exactly "
                            f"{json.dumps(list(LABELS))}")
        if trusted_seen[0]:
            findings.append(f"{TRUSTED_VARIABLE} is set on a private repository: it is for trusted dispatch of a public one")
        mode = "standing"
    else:
        for runner in standing:
            findings.append(f"public repository with a standing runner {runner['name']}: a fork's job would reach it "
                            f"(decision 0080; `factory-ci deregister {repository}`)")
        if seen[0]:
            findings.append(f"public repository with {RUNS_ON_VARIABLE} set: every fork pull request would ask for it")
        if not (trusted_seen[1] is not None and exact(trusted_seen[1])):
            findings.append(f"{TRUSTED_VARIABLE} is "
                            f"{'not set' if not trusted_seen[0] else repr(variables[TRUSTED_VARIABLE]) + ', not exactly ' + json.dumps(list(LABELS))}"
                            f": a public repository's owner runs reach the VM only through it (`factory-ci trust`, `enable`)")
        mode = "dispatch"
    if not paths:
        findings.append(f"no workflow on {branch}: nothing in the repository asks for a runner")
    listed_jobs = [item for item in (load_hosted_jobs() if hosted_jobs is None else hosted_jobs)
                   if str(item.get("repository")).casefold() == repository.casefold()]
    for item in listed_jobs:
        path, job = item.get("workflow"), item.get("job")
        where = f"runners.json lists {path} job {job} as deliberately hosted ({item.get('reason')})"
        found = next((e for e in workflows if e["path"] == path and e["job"] == job), None)
        if private:
            findings.append(f"{where}, but {repository} is private: only a public repository may have a hosted job "
                            f"(decision 0084), and a private one's jobs run on the VM")
        elif found is None:
            findings.append(f"{where}, but there is no such job on {branch}: remove the entry (a stale entry would "
                            f"exempt whatever is written there next)")
        elif found["runs_on"] != item.get("runs_on"):
            findings.append(f"{where} with runs-on {item.get('runs_on')!r}, but it now has runs-on {found['runs_on']!r}")
        else:
            found["ok"], found["hosted"] = "hosted", item.get("reason")
    for entry in workflows:
        if entry["ok"] is False:
            where = f"{entry['path']}: " + (f"job {entry['job']}" if entry["job"] else "no job could be read")
            findings.append(f"{where} has runs-on {entry['runs_on']!r}, not the contract line (RUNS_ON_LINE): a literal "
                            f"label bypasses the repository's variables, and a hosted one is a silent fallback "
                            f"(a job that stays hosted on purpose is listed in runners.json)")
    return {
        "schema": SCHEMA, "repository": repository, "visibility": visibility, "default_branch": branch,
        "checked_at": now() if callable(now) else (now or now_utc()),
        "verdict": "fail" if findings else "pass", "findings": findings, "runners": listed,
        "routing": {"mode": mode, "expected": list(LABELS),
                    RUNS_ON_VARIABLE: variables.get(RUNS_ON_VARIABLE), TRUSTED_VARIABLE: variables.get(TRUSTED_VARIABLE)},
        "workflows": workflows,
    }


# ------------------------------------------------------------------------------------- the guest --

def ask_guest(guest, *args, stdin=None):
    try:
        return guest.call(*args, stdin=stdin)
    except Exception as error:
        raise Failed(f"the guest could not be asked `{args[0]}` ({type(error).__name__}: {error}); is the VM up "
                     f"(`factory-ci status`), and is its kit current (`factory-ci setup`)?") from error


def held_by(guest, name, repository):
    """What this guest's account for `name` is registered as, {"id", "url"}, or None when it holds nothing.
    The file is the account's to write, so each value is checked for its shape and used as data."""
    for line in ask_guest(guest, "held", name).splitlines():
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if isinstance(item, dict) and item.get("kind") == "held" and re.fullmatch(r"[0-9]{1,19}", str(item.get("agentId"))):
            return {"id": int(item["agentId"]), "url": str(item.get("url"))}
    return None


def plan(repository, github, guest, vm):
    """The repository's runner named `vm` (GitHub's record) or None; Refused when registering would replace
    a runner this guest does not hold, or an account's registration for another repository."""
    name = name_of(repository)
    if not dispatch.NAME.fullmatch(name):
        raise Refused(f"{repository}: the guest cannot name an account for it ({name!r}: 1-24 of a-z, 0-9, -)")
    runners = pages(github, "the repository's runners", f"/repos/{repository}/actions/runners", "runners")
    named = [r for r in runners if r.get("name") == vm]
    held = held_by(guest, name, repository)
    if held and held["url"].casefold() != f"https://github.com/{repository}".casefold():
        raise Refused(f"the guest's account fci-{name} is registered for {held['url']}, not {repository}: not replacing it")
    if named and (not held or held["id"] != named[0].get("id")):
        raise Refused(f"{repository} has a runner named {vm} (id {named[0].get('id')}) that this guest does not hold "
                      f"(another host's registration, or one from before a rebuild): not replacing it; remove it on "
                      f"GitHub if it is stale")
    return named[0] if named else None


# ------------------------------------------------------------------------------------- onboard --

def public_message(repository):
    return (f"{repository} is public: a standing runner would take a fork's job (decision 0080). Serve it by dispatch "
            f"instead: `factory-ci trust {repository}`, then `factory-ci enable {repository}`")


def onboard(repository, github, guest, vm, now=None, log=print, wait=0, sleep=time.sleep, interval=3):
    """Register this host's runner for a private `repository` unless it holds a correct one, set
    FACTORY_RUNS_ON unless it is exact, then verify. Returns the record; it never touches another
    host's runner."""
    check_repository(repository)
    if vm not in authorized_names():
        raise Refused(f"{vm} is not an authorized runner VM (tools/ci-runner/runners.json lists "
                      f"{', '.join(authorized_names())}); adding a host is a reviewed change to that file")
    repo = read(github, "the repository", f"/repos/{repository}")
    if (repo or {}).get("private") is not True:
        if (repo or {}).get("private") is False:
            raise Refused(public_message(repository))
        raise Unreadable(f"could not read the repository (/repos/{repository}): GitHub did not say whether it is private")
    existing = plan(repository, github, guest, vm)
    changed = False
    if existing and existing.get("status") == "online" and exact(existing.get("labels")):
        log(f"{vm} is already registered for {repository} (runner {existing.get('id')}, online): not registering again")
    else:
        token = (write(github, "get a registration token", "POST", f"/repos/{repository}/actions/runners/registration-token") or {}).get("token")
        if not token:
            raise Failed(f"GitHub gave no registration token for {repository}; the credential needs {permission('/actions/runners/registration-token')}")
        ask_guest(guest, "register", name_of(repository), repository, stdin=token + "\n")
        log(f"registered {vm} for {repository}" + (" (replacing its own offline or mislabelled registration)" if existing else ""))
        changed = True
    variables = {item.get("name"): item.get("value") for item in
                 pages(github, "the repository's variables", f"/repos/{repository}/actions/variables", "variables", size=30)}
    have = variable_value(variables, RUNS_ON_VARIABLE)
    if have[1] is None or not exact(have[1]):
        body = {"name": RUNS_ON_VARIABLE, "value": json.dumps(list(LABELS), separators=(",", ":"))}
        if have[0]:
            write(github, f"set {RUNS_ON_VARIABLE}", "PATCH", f"/repos/{repository}/actions/variables/{RUNS_ON_VARIABLE}", body)
        else:
            write(github, f"set {RUNS_ON_VARIABLE}", "POST", f"/repos/{repository}/actions/variables", body)
        log(f"{RUNS_ON_VARIABLE} set to {body['value']}")
        changed = True
    record = verify(repository, github, now=now)
    waited = 0
    while changed and record["verdict"] == "fail" and waited < wait:  # a new runner takes seconds to show online
        sleep(interval)
        waited += interval
        record = verify(repository, github, now=now)
    return record


# ------------------------------------------------------------------------------------------ CLI --

def write_record(path, record):
    directory = os.path.dirname(os.path.abspath(path))
    handle, temporary = tempfile.mkstemp(dir=directory, prefix=".onboarding-", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            json.dump(record, out, indent=2, sort_keys=True)
            out.write("\n")
        os.replace(temporary, path)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise


def report(record, out=None):
    out = out or sys.stdout
    for finding in record["findings"]:
        print(f"  X   {finding}", file=out)
    for entry in record["workflows"]:
        if entry["ok"] is None:
            print(f"  note {entry['path']}: job {entry['job']} uses {entry['uses']} and names no runner of its own: "
                  f"the called workflow decides", file=out)
    for entry in record["workflows"]:
        if entry["ok"] == "hosted":
            print(f"  note {entry['path']}: job {entry['job']} stays on {entry['runs_on']} on purpose "
                  f"({entry['hosted']}; listed in runners.json)", file=out)
    print(f"onboarding of {record['repository']} ({record['visibility']}): {record['verdict']}, "
          f"{len(record['findings'])} finding(s)", file=out)


def github_client():
    try:
        return dispatch.GitHub()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as error:
        raise Failed("no GitHub login: `gh auth login` as the repository's owner, with repository administration "
                     f"(Administration, Variables and Contents) ({type(error).__name__}: {error})") from error


def main(argv):
    command = argv[0] if argv else ""
    usage = "usage: onboard.py check OWNER/REPO [--json FILE] | onboard OWNER/REPO | guard OWNER/REPO"
    try:
        if command == "check" and len(argv) in (2, 4) and (len(argv) == 2 or argv[2] == "--json"):
            record = verify(argv[1], github_client())
            if len(argv) == 4:
                write_record(argv[3], record)
            report(record)
            return 0 if record["verdict"] == "pass" else 1
        if command == "onboard" and len(argv) == 2:
            record = onboard(argv[1], github_client(), dispatch.Guest(), dispatch.VM, wait=90)
            report(record)
            return 0 if record["verdict"] == "pass" else 1
        if command == "guard" and len(argv) == 2:
            check_repository(argv[1])
            plan(argv[1], github_client(), dispatch.Guest(), dispatch.VM)
            return 0
    except Refused as error:
        print(f"onboard: refused: {error}", file=sys.stderr)
        return 1
    except OnboardError as error:
        print(f"onboard: {error}", file=sys.stderr)
        return 2
    print(usage, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
