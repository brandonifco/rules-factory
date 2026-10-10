#!/usr/bin/env python3
"""dispatch -- the trusted dispatcher that lets a public repository's own runs use factory-ci (0080).

A runner registered with a public repository takes any job whose `runs-on` its labels satisfy, and
a fork's pull request writes its own `runs-on`. So no runner is ever registered with a public
repository for longer than one job, and none exists until this program has admitted the job it is
for. It runs on the KVM host as the owner, with the owner's `gh` login, which never reaches the
guest. Every POLL seconds, for each repository the guest serves by dispatch:

  1. It reads the runs GitHub holds and their unfinished jobs. A job any of whose labels is not one
     of factory-ci's is somebody else's (a hosted job) and is ignored; every other job could be
     handed to a factory-ci runner and is judged.
  2. `judge` admits a run only if all of these hold, read from GitHub's record of the run and never
     from the workflow file: its head repository is this repository, not a fork; it was started,
     and if re-run re-started, by the repository's owner; its event is one whose code is the
     repository's own (no `pull_request_target`, `workflow_run`, comment or review event); and its
     exact head commit was put on its branch by the owner, by the repository's activity record.
     A run that fails is cancelled. Its jobs never had a runner to go to, and while any is still
     queued no runner is started for that repository at all.
  3. For an admitted run it writes an admission into the guest, root-owned, which the guest's
     job-started hook requires, and starts one one-job (JIT) runner per admitted queued job, with
     exactly factory-ci's labels, as one of that repository's two accounts that has no runner up:
     an account never has two, so no job shares its UID with a listener still waiting for one.
  4. It deletes every waiting runner of a repository the moment anything there is refused, or a
     cycle cannot read GitHub whole (a list it could not page through to the end, an error); it
     deletes one left idle, stops a guest runner GitHub no longer knows, and has the guest reap
     finished ones. The guest refuses a job a runner got more than 15 minutes after it started,
     so a waiting runner outlives a dead dispatcher by no more than that.

The two job slots in the guest still bound how many jobs run at once; a one-job runner adds no
capacity. `judge` is pure and is what the tests hold; everything else is I/O around it.

Usage:
  dispatch.py run                      the dispatcher loop (factory-ci dispatch; a user service)
  dispatch.py audit                    the boundary as one: registrations, visibility, variables,
                                       fork approval; exit 1 on any finding (factory-ci audit)
  dispatch.py timings OWNER/REPO [N]   queue and run time of the last N runs' jobs, by runner
  dispatch.py check                    prove the dispatcher's token file can do everything the
                                       dispatcher does, on every served repository

The dispatcher authenticates with the token in TOKEN_FILE (~/.config/factory-ci/dispatch-token, or
$FACTORY_CI_DISPATCH_TOKEN_FILE) when that file exists, and with the owner's `gh` login otherwise.
`gh` keeps its token in the desktop keyring, which is locked until a graphical login, so a service
that starts at boot needs the file: a fine-grained token scoped to the served repositories, with
Actions read/write, Administration read/write, Contents read and Metadata read. `audit` and
`timings` read every repository and always use `gh`.
Standard library only.
"""
import json
import os
import re
import secrets
import shlex
import stat
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

KIT = os.path.dirname(os.path.abspath(__file__))
FACTORY_CI = os.path.join(KIT, "factory-ci")
VM = os.environ.get("FACTORY_CI_VM", "factory-ci-1")
LABELS = ("self-hosted", "linux", "x64", "factory-ci")
POLL = float(os.environ.get("FACTORY_CI_DISPATCH_POLL", "10"))
JIT_MAX = int(os.environ.get("FACTORY_CI_JIT_MAX", "4"))
IDLE_MAX = 60
STARTING = 120
PENDING_GRACE = 120
API = "https://api.github.com"
TOKEN_FILE = os.environ.get("FACTORY_CI_DISPATCH_TOKEN_FILE", os.path.expanduser("~/.config/factory-ci/dispatch-token"))

#: Events whose workflow and code are the repository's own revision. Excluded on purpose: the
#: events that run a trusted workflow for somebody else's change (`pull_request_target`,
#: `workflow_run`) or that anyone may cause (`issue_comment`, reviews, discussions, forks, stars).
EVENTS = frozenset({"push", "pull_request", "workflow_dispatch", "schedule", "status", "issues"})
#: Events whose run is the default branch's latest commit and may carry no branch of its own.
DEFAULT_BRANCH_EVENTS = frozenset({"schedule", "status", "issues"})
#: How a commit comes to be at the tip of a branch, in GitHub's activity record.
PLACEMENTS = frozenset({"push", "force_push", "branch_creation", "pr_merge", "merge_queue_merge"})


def ours(labels):
    """Whether a factory-ci runner could be handed a job asking for these labels: GitHub matches a
    job to a runner whose labels include every one the job names, ignoring case."""
    wanted = {label.casefold() for label in labels or ()}
    return bool(wanted) and wanted <= {label.casefold() for label in LABELS}


def login(user):
    return ((user or {}).get("login") or "").casefold()


def judge(repository, run, activity):
    """("admit" | "refuse" | "pending", why) for one workflow run of `repository` (OWNER/REPO).

    `run` is GitHub's record of the run (GET /repos/{r}/actions/runs/{id}); `activity` is the
    repository's activity for the run's branch (GET /repos/{r}/activity?ref=...), newest first, or
    None when it was not read. Nothing here comes from a workflow file or a job's own output.
    "pending" means the commit's placement is not in the record yet, which GitHub can lag; the
    caller refuses a run still pending after a grace period.
    """
    owner = repository.split("/", 1)[0].casefold()
    name = repository.casefold()
    if ((run.get("repository") or {}).get("full_name") or "").casefold() != name:
        return "refuse", f"the run belongs to {(run.get('repository') or {}).get('full_name')}, not {repository}"
    head = ((run.get("head_repository") or {}).get("full_name") or "")
    if head.casefold() != name:
        return "refuse", f"its code comes from {head or 'a repository that no longer exists'}, not {repository}"
    event = run.get("event") or ""
    if event not in EVENTS:
        return "refuse", f"its event, {event or 'none'}, is not one whose runs are admitted ({', '.join(sorted(EVENTS))})"
    for role in ("actor", "triggering_actor"):
        if login(run.get(role)) != owner:
            return "refuse", f"its {role.replace('_', ' ')} is {login(run.get(role)) or 'nobody'}, not the owner {owner}"
    sha = run.get("head_sha") or ""
    if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        return "refuse", f"its head commit {sha!r} is not a full commit id"
    branch = branch_of(run)
    if not branch:
        return "refuse", f"a {event} run on no branch cannot be traced to a push"
    if activity is None:
        return "pending", f"the activity of {branch} has not been read"
    placed = [item for item in activity
              if item.get("after") == sha and item.get("activity_type") in PLACEMENTS
              and (item.get("ref") or "") in (branch, f"refs/heads/{branch}")]
    if any(login(item.get("actor")) == owner for item in placed):
        return "admit", f"{event} by {owner} at {sha[:12]} on {branch}, which {owner} put there"
    if placed:
        who = ", ".join(sorted({login(item.get("actor")) or "nobody" for item in placed}))
        return "refuse", f"{sha[:12]} was put on {branch} by {who}, not by the owner"
    return "pending", f"no record yet of who put {sha[:12]} on {branch}"


def branch_of(run):
    branch = run.get("head_branch")
    if not branch and run.get("event") in DEFAULT_BRANCH_EVENTS:
        branch = (run.get("repository") or {}).get("default_branch")
    return branch


# ---------------------------------------------------------------------------------------- I/O --

NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,23}")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
LANES = (("a", "fci-"), ("b", "fcj-"))


class Incomplete(Exception):
    """GitHub's answer could not be read whole: nothing is started on a partial view."""


def log(message):
    print(f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ} {message}", flush=True)


def read_token_file(path):
    """The token in `path`, or None when there is no such file. A credential: refused unless it is a
    regular file of the running user's that no one else can read or write."""
    try:
        found = os.lstat(path)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(found.st_mode) or found.st_uid != os.getuid() or found.st_mode & 0o077:
        raise PermissionError(f"{path} must be a regular file of yours with mode 0600 (chmod 600 {path})")
    with open(path, encoding="utf-8") as handle:
        token = handle.read().strip()
    if not token or any(c.isspace() for c in token):
        raise ValueError(f"{path} must hold one token and nothing else")
    return token


class GitHub:
    """The REST API as the owner. List reads are conditional: GitHub does not count a 304.

    With `token_file`, the token is read from that file when it exists (see the module's note);
    otherwise, and always without it, from the owner's `gh` login."""

    def __init__(self, token_file=None):
        self.token_file = token_file
        self.token = self._token()
        self.etags = {}
        self.link = ""

    def _token(self):
        token = read_token_file(self.token_file) if self.token_file else None
        self.source = self.token_file if token else "the gh login"
        return token or subprocess.run(["gh", "auth", "token"], check=True, capture_output=True, text=True).stdout.strip()

    def call(self, method, path, body=None, cache=False):
        url = path if path.startswith("http") else API + path
        for attempt in (1, 2):
            request = urllib.request.Request(url, method=method, data=None if body is None else json.dumps(body).encode())
            request.add_header("Authorization", f"Bearer {self.token}")
            request.add_header("Accept", "application/vnd.github+json")
            request.add_header("X-GitHub-Api-Version", "2022-11-28")
            if body is not None:
                request.add_header("Content-Type", "application/json")
            if cache and url in self.etags:
                request.add_header("If-None-Match", self.etags[url][0])
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    data = response.read()
                    value = json.loads(data) if data else None
                    self.link = response.headers.get("Link") or ""
                    if cache and response.headers.get("ETag"):
                        self.etags[url] = (response.headers["ETag"], value, self.link)
                    return value
            except urllib.error.HTTPError as error:
                if error.code == 304 and cache:
                    self.link = self.etags[url][2]
                    return self.etags[url][1]
                if error.code == 401 and attempt == 1:
                    self.token = self._token()
                    continue
                raise

    def get(self, path, cache=False):
        return self.call("GET", path, cache=cache)

    def every(self, path, key, cache=True, pages=10):
        """Every item of a paginated list, or Incomplete: a list GitHub cut is not a list."""
        items, separator = [], "&" if "?" in path else "?"
        for page in range(1, pages + 1):
            chunk = self.get(f"{path}{separator}per_page=100&page={page}", cache=cache)
            batch = chunk.get(key, []) if isinstance(chunk, dict) else chunk
            items.extend(batch)
            if len(batch) < 100:
                return items
        raise Incomplete(f"{path} has more than {pages * 100} {key}")

    def next_link(self):
        found = re.search(r'<([^>]+)>;\s*rel="next"', self.link or "")
        return found.group(1) if found else None


class Guest:
    """The guest's half, `dispatch-guest`, through the kit's own `factory-ci ssh`. Every argument is
    checked here and quoted: the remote side is a shell running as the guest's admin."""

    @staticmethod
    def call(*args, stdin=None):
        for arg in args:
            if not re.fullmatch(r"[A-Za-z0-9._/-]+", arg):
                raise ValueError(f"refusing to send {arg!r} to the guest")
        command = "sudo /opt/factory-ci/bin/dispatch-guest " + " ".join(shlex.quote(a) for a in args)
        result = subprocess.run([FACTORY_CI, "ssh", command], input=stdin, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"guest {args[0]}: {result.stderr.strip() or result.stdout.strip()}")
        return result.stdout

    def inventory(self):
        return parse_inventory(self.call("inventory"))


def parse_inventory(text):
    """{"dispatch": {name: repo}, "persistent": {account: url}, "jit": {(name, runner id): (account, state)}}.

    GitHub numbers runners per repository, so a guest runner is known by its repository's name and
    its id together.

    One JSON object per line; a line that is not one, or whose fields do not have their shape, is
    dropped. A persistent runner's URL comes from a file its account can write, so it is data here
    and never a name the dispatcher acts on."""
    found = {"dispatch": {}, "persistent": {}, "jit": {}}
    for line in text.splitlines():
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if not isinstance(item, dict):
            continue
        kind = item.get("kind")
        if kind == "dispatch" and NAME.fullmatch(str(item.get("name"))) and REPOSITORY.fullmatch(str(item.get("repo"))):
            found["dispatch"][item["name"]] = item["repo"]
        elif kind == "persistent" and re.fullmatch(r"fci-[a-z0-9][a-z0-9-]{0,23}", str(item.get("account"))):
            found["persistent"][item["account"]] = str(item.get("url"))
        elif kind == "jit" and re.fullmatch(r"[0-9]{1,19}", str(item.get("id"))) and NAME.fullmatch(str(item.get("name"))) \
                and re.fullmatch(r"fc[ij]-[a-z0-9][a-z0-9-]{0,23}", str(item.get("account"))):
            found["jit"][(item["name"], int(item["id"]))] = (item["account"], str(item.get("state")))
    return found


class Dispatcher:
    def __init__(self, github=None, guest=None):
        self.github = github or GitHub(token_file=TOKEN_FILE)
        self.guest = guest or Guest()
        self.verdicts = {}      # (repository, run id, attempt) -> (verdict, why, first seen)
        self.cancels = {}       # (repository, run id, attempt) -> cancel requests made
        self.admitted = {}      # name -> the run-attempts last written into the guest
        self.spawned = {}       # (name, runner id) -> (repository, account, monotonic time started)
        self.seen = set()       # (name, runner id) this program started that GitHub has listed
        self.idle_since = {}    # (name, runner id) -> monotonic time first seen online and idle
        self.inventory = None
        self.inventory_at = 0.0

    def refresh(self):
        if self.inventory is None or time.monotonic() - self.inventory_at > 60:
            self.inventory = self.guest.inventory()
            self.inventory_at = time.monotonic()
        else:
            self.inventory["jit"] = self.guest.inventory()["jit"]

    def candidates(self, repository):
        """[(run, job)] for every unfinished job in `repository` a factory-ci runner could take."""
        runs = {}
        for status in ("queued", "in_progress", "waiting", "pending", "requested"):
            for run in self.github.every(f"/repos/{repository}/actions/runs?status={status}", "workflow_runs"):
                runs[run["id"]] = run
        found = []
        for run in runs.values():
            for job in self.github.every(f"/repos/{repository}/actions/runs/{run['id']}/attempts/{run['run_attempt']}/jobs", "jobs"):
                if job.get("status") not in ("completed", "in_progress") and ours(job.get("labels")):
                    found.append((run, job))
        return found

    def activity(self, repository, branch, sha):
        """The branch's activity, newest first, far enough back to find `sha` (three pages at most)."""
        ref = urllib.parse.quote(f"refs/heads/{branch}", safe="")
        path, items = f"/repos/{repository}/activity?ref={ref}&per_page=100", []
        for _ in range(3):
            chunk = self.github.get(path)
            items.extend(chunk)
            path = self.github.next_link()
            if not path or any(item.get("after") == sha for item in chunk):
                break
        return items

    def verdict(self, repository, run):
        key = (repository, run["id"], run["run_attempt"])
        held = self.verdicts.get(key)
        if held and held[0] != "pending":
            return held[0], held[1]
        activity = None
        branch = branch_of(run)
        if branch and ((run.get("head_repository") or {}).get("full_name") or "").casefold() == repository.casefold():
            activity = self.activity(repository, branch, run.get("head_sha"))
        verdict, why = judge(repository, run, activity)
        first = held[2] if held else time.monotonic()
        if verdict == "pending" and time.monotonic() - first > PENDING_GRACE:
            verdict, why = "refuse", why + f", still after {PENDING_GRACE}s"
        if verdict != "pending" or not held:
            log(f"{repository} run {run['id']} attempt {run['run_attempt']} ({run.get('name')}): {verdict}: {why}")
        self.verdicts[key] = (verdict, why, first)
        return verdict, why

    def cancel(self, repository, run):
        """Ask until GitHub has finished the run; past three asks, force it."""
        key = (repository, run["id"], run["run_attempt"])
        asked = self.cancels.get(key, 0)
        how = "force-cancel" if asked >= 3 else "cancel"
        self.cancels[key] = asked + 1
        try:
            self.github.call("POST", f"/repos/{repository}/actions/runs/{run['id']}/{how}")
            if asked == 0 or how == "force-cancel":
                log(f"{repository} run {run['id']} attempt {run['run_attempt']}: {how} asked; it wanted factory-ci and was not admitted")
        except urllib.error.HTTPError as error:
            if error.code != 409:  # 409: already finishing
                log(f"{repository} run {run['id']}: {how} failed: HTTP {error.code}")

    def lanes(self, name):
        return [(lane, prefix + name) for lane, prefix in LANES]

    def serve(self, name, repository, live):
        """Judge every job in `repository` a factory-ci runner could take, and start runners for the
        admitted queued ones; returns how many runners it started."""
        runners = self.github.every(f"/repos/{repository}/actions/runners", "runners")
        mine = {r["id"]: r for r in runners if r["name"].startswith(f"{VM}-jit-")}
        foreign = [r["name"] for r in runners if r["id"] not in mine]
        if foreign:
            self.retire_waiting(name, repository, mine, "a runner registered outside dispatch")
            log(f"{repository}: NOT SERVED: runner(s) {', '.join(foreign)} registered outside dispatch; "
                f"a public repository has none (factory-ci audit)")
            return 0
        admitted, demand, blocked = set(), 0, False
        for run, job in self.candidates(repository):
            verdict, _ = self.verdict(repository, run)
            if verdict == "admit":
                admitted.add(f"{run['id']}-{run['run_attempt']}")
                demand += job.get("status") == "queued"
                continue
            blocked = True
            if verdict == "refuse":
                self.cancel(repository, run)
        # Written whenever the set changes, so a runner already waiting can take a new admitted job.
        if admitted and admitted != self.admitted.get(name):
            self.guest.call("admit", name, *sorted(admitted))
        self.admitted[name] = admitted
        now = time.monotonic()
        up = {runner_id for (owner, runner_id), (account, state) in self.inventory["jit"].items()
              if owner == name and state == "active"}
        up |= {runner_id for (owner, runner_id), (_, _, started) in self.spawned.items()
               if owner == name and (name, runner_id) not in self.seen and now - started < STARTING}
        self.seen |= {(name, runner_id) for runner_id in mine} & set(self.spawned)
        supply = 0
        for runner_id, runner in mine.items():
            if runner.get("busy"):
                self.idle_since.pop((name, runner_id), None)
            elif runner.get("status") == "online":
                supply += 1
                self.idle_since.setdefault((name, runner_id), now)
            elif runner_id in up:
                supply += 1
        supply += sum(1 for (owner, runner_id), (_, _, started) in self.spawned.items()
                      if owner == name and runner_id not in mine and (name, runner_id) not in self.seen
                      and now - started < STARTING)
        if blocked:
            self.retire_waiting(name, repository, mine, "a job that was not admitted is unfinished")
            if demand:
                log(f"{repository}: {demand} admitted job(s) wait: no runner starts while a job that was not admitted is unfinished")
            return 0
        for runner_id in [r for (owner, r) in self.idle_since
                          if owner == name and r in mine and demand <= supply - 1 and now - self.idle_since[(owner, r)] > IDLE_MAX]:
            self.retire(name, repository, runner_id, f"idle for {IDLE_MAX}s with nothing admitted for it")
            supply -= 1
        busy_accounts = {self.spawned.get((name, r), (None, None))[1] for r in up} | {
            account for (account, state) in self.inventory["jit"].values() if state == "active"}
        free = [(lane, account) for lane, account in self.lanes(name) if account not in busy_accounts]
        wanted = free[:max(0, min(demand - supply, JIT_MAX - live))]
        if wanted:  # again, so an admission lost with a guest reboot is back before a runner starts
            self.guest.call("admit", name, *sorted(admitted))
        started = 0
        for lane, account in wanted:
            self.spawn(name, lane, account, repository)
            started += 1
        return started

    def spawn(self, name, lane, account, repository):
        runner_name = f"{VM}-jit-{secrets.token_hex(4)}"
        created = self.github.call("POST", f"/repos/{repository}/actions/runners/generate-jitconfig",
                                   {"name": runner_name, "runner_group_id": 1, "labels": list(LABELS), "work_folder": "_work"})
        runner_id = created["runner"]["id"]
        try:
            self.guest.call("start", name, lane, str(runner_id), stdin=created["encoded_jit_config"] + "\n")
        except Exception:
            self.github.call("DELETE", f"/repos/{repository}/actions/runners/{runner_id}")
            raise
        self.spawned[(name, runner_id)] = (repository, account, time.monotonic())
        log(f"{repository}: started one-job runner {runner_name} (id {runner_id}) as {account}")

    def retire_waiting(self, name, repository, mine, why):
        """Every runner of `repository` not running a job goes: none waits beside a refused job."""
        for runner_id, runner in mine.items():
            if not runner.get("busy"):
                self.retire(name, repository, runner_id, why)

    def retire(self, name, repository, runner_id, why):
        try:
            self.github.call("DELETE", f"/repos/{repository}/actions/runners/{runner_id}")
        except urllib.error.HTTPError as error:
            if error.code != 404:
                log(f"{repository}: could not delete runner {runner_id}: HTTP {error.code}")
                return
        self.guest.call("stop", name, str(runner_id))
        self.spawned.pop((name, runner_id), None)
        self.idle_since.pop((name, runner_id), None)
        log(f"{repository}: retired one-job runner {runner_id} ({why})")

    def reconcile(self):
        """A guest runner GitHub no longer knows is stopped; a finished one is reaped."""
        now = time.monotonic()
        for name, repository in self.inventory["dispatch"].items():
            runners = self.github.every(f"/repos/{repository}/actions/runners", "runners")
            known = {r["id"] for r in runners}
            for r in runners:
                if r["name"].startswith(f"{VM}-jit-") and (name, r["id"]) not in self.inventory["jit"] \
                        and now - self.spawned.get((name, r["id"]), ("", "", 0.0))[2] > STARTING and r.get("status") != "online":
                    self.retire(name, repository, r["id"], "no guest runner")
            for (owner, runner_id), (account, state) in self.inventory["jit"].items():
                if owner == name and state == "active" and runner_id not in known \
                        and now - self.spawned.get((name, runner_id), ("", "", 0.0))[2] > STARTING:
                    self.guest.call("stop", name, str(runner_id))
                    log(f"{account}: stopped guest runner {runner_id} of {repository}, which GitHub no longer knows")
        if any(state != "active" for _, state in self.inventory["jit"].values()):
            self.guest.call("reap")
        for key in [k for k, (_, _, t) in self.spawned.items() if now - t > 8 * 3600]:
            self.spawned.pop(key, None)
            self.seen.discard(key)

    def cycle(self):
        self.refresh()
        live = sum(1 for _, state in self.inventory["jit"].values() if state == "active")
        for name, repository in sorted(self.inventory["dispatch"].items()):
            try:
                live += self.serve(name, repository, live)
            except (urllib.error.URLError, RuntimeError, KeyError, ValueError, Incomplete) as error:
                log(f"{repository}: this cycle failed, so its waiting runners go: {error}")
                try:
                    runners = self.github.every(f"/repos/{repository}/actions/runners", "runners")
                    self.retire_waiting(name, repository, {r["id"]: r for r in runners if r["name"].startswith(f"{VM}-jit-")},
                                        "the cycle could not judge everything")
                except Exception as again:  # the guest's lease is the backstop
                    log(f"{repository}: could not retire waiting runners: {again}")
        self.reconcile()


def run_forever():
    dispatcher = Dispatcher()
    log(f"dispatcher up: VM {VM}, labels {','.join(LABELS)}, poll {POLL}s, at most {JIT_MAX} one-job runners, "
        f"token from {dispatcher.github.source}")
    while True:
        started = time.monotonic()
        try:
            dispatcher.cycle()
        except Exception as error:  # the loop outlives one bad cycle; systemd restarts it if it dies
            log(f"cycle failed: {type(error).__name__}: {error}")
        time.sleep(max(1.0, POLL - (time.monotonic() - started)))


# -------------------------------------------------------------------------------------- audit --

def audit(github=None, guest=None):
    """Registrations, labels, visibility, variables and fork approval, reviewed as one boundary."""
    github = github or GitHub()
    inventory = (guest or Guest()).inventory()
    findings, notes = [], []
    owner = github.get("/user")["login"]
    public = {r["full_name"]: r for r in paginate(github, f"/user/repos?affiliation=owner&visibility=public&per_page=100")}
    for account, url in sorted(inventory["persistent"].items()):
        repository = url.removeprefix("https://github.com/")
        if github.get(f"/repos/{repository}")["private"] is not True:
            findings.append(f"{repository}: a standing runner registration ({account}) on a repository that is not private")
        else:
            notes.append(f"{repository}: private, standing runner ({account})")
    for name, repository in sorted(inventory["dispatch"].items()):
        policy = github.get(f"/repos/{repository}/actions/permissions/fork-pr-contributor-approval").get("approval_policy")
        if policy != "all_external_contributors":
            findings.append(f"{repository}: fork pull requests from outside contributors run without approval ({policy})")
        variables = {v["name"]: v["value"] for v in github.get(f"/repos/{repository}/actions/variables?per_page=30").get("variables", [])}
        trusted = variables.get("FACTORY_RUNS_ON_TRUSTED")
        try:
            value = json.loads(trusted) if trusted is not None else list(LABELS)
        except ValueError:
            value = trusted
        if sorted(str(v).casefold() for v in (value if isinstance(value, list) else [value])) != sorted(LABELS):
            findings.append(f"{repository}: FACTORY_RUNS_ON_TRUSTED is {trusted}, not factory-ci's labels")
        notes.append(f"{repository}: dispatch (fci-{name}, fcj-{name}), FACTORY_RUNS_ON_TRUSTED {'set' if trusted else 'unset'}, fork approval {policy}")
    for repository in sorted(public):
        runners = github.get(f"/repos/{repository}/actions/runners?per_page=100").get("runners", [])
        standing = [r["name"] for r in runners if not r["name"].startswith(f"{VM}-jit-")]
        if standing:
            findings.append(f"{repository}: public, with standing runner(s) {', '.join(standing)}")
        variables = {v["name"] for v in github.get(f"/repos/{repository}/actions/variables?per_page=30").get("variables", [])}
        if "FACTORY_RUNS_ON" in variables:
            findings.append(f"{repository}: public, with FACTORY_RUNS_ON set: every fork pull request would ask for it")
        if "FACTORY_RUNS_ON_TRUSTED" in variables and repository not in inventory["dispatch"].values():
            findings.append(f"{repository}: FACTORY_RUNS_ON_TRUSTED set, but the guest does not serve it by dispatch")
    for line in notes:
        print(f"  ok  {line}")
    for line in findings:
        print(f"  X   {line}")
    print(f"audit of {owner}'s repositories: {len(findings)} finding(s)")
    return 1 if findings else 0


def paginate(github, path):
    page, items = 1, []
    while True:
        chunk = github.get(f"{path}&page={page}")
        items.extend(chunk)
        if len(chunk) < 100:
            return items
        page += 1


# ------------------------------------------------------------------------------------ timings --

def timings(repository, count=10):
    """Queue and run time of the last `count` finished runs' jobs, grouped by job and runner kind."""
    github = GitHub()
    runs = github.get(f"/repos/{repository}/actions/runs?status=completed&per_page={count}")["workflow_runs"]
    groups = {}
    print(f"{'run':>12} {'workflow/job':<38} {'runner':<26} {'queue':>6} {'run':>6} conclusion")
    for run in runs:
        for job in github.get(f"/repos/{repository}/actions/runs/{run['id']}/attempts/{run['run_attempt']}/jobs")["jobs"]:
            if not job.get("started_at") or not job.get("completed_at") or not job.get("runner_name"):
                continue  # a job that never had a runner (cancelled while queued) measures nothing
            created, started, done = (datetime.fromisoformat(job[k].replace("Z", "+00:00")) for k in ("created_at", "started_at", "completed_at"))
            queue, took = (started - created).total_seconds(), (done - started).total_seconds()
            runner = job.get("runner_name") or "-"
            kind = "factory-ci" if runner.startswith(VM) else "hosted"
            print(f"{run['id']:>12} {(run['name'] + '/' + job['name'])[:38]:<38} {runner[:26]:<26} {queue:>5.0f}s {took:>5.0f}s {job.get('conclusion')}")
            groups.setdefault((run["name"], job["name"], run["event"], kind), []).append((queue, took))
    print()
    for (workflow, job, event, kind), values in sorted(groups.items()):
        print(f"median {workflow}/{job} ({event}) on {kind}: queue {statistics.median(v[0] for v in values):.0f}s, "
              f"run {statistics.median(v[1] for v in values):.0f}s over {len(values)} job(s)")
    return 0


def check(guest=None):
    """Everything the dispatcher asks of GitHub, asked with the token file, on every served repository.

    Reads are read; the two writes are proven without effect: a cancel of a finished run (GitHub
    answers 409 when it may cancel, 403 or 404 when it may not), and a one-job runner created and
    deleted at once, never started, so it never takes a job."""
    token = read_token_file(TOKEN_FILE)
    if token is None:
        print(f"no token file at {TOKEN_FILE}: the dispatcher uses the gh login, which a boot cannot unlock")
        return 1
    github = GitHub(token_file=TOKEN_FILE)
    served = (guest or Guest()).inventory()["dispatch"]
    failures = 0

    def step(repository, what, call, accept=()):
        nonlocal failures
        try:
            call()
            print(f"  ok  {repository}: {what}")
        except urllib.error.HTTPError as error:
            if error.code in accept:
                print(f"  ok  {repository}: {what} (HTTP {error.code}, as expected)")
            else:
                failures += 1
                print(f"  X   {repository}: {what}: HTTP {error.code} {error.reason}")

    for name, repository in sorted(served.items()):
        runs = []
        step(repository, "read workflow runs (Actions: read)",
             lambda: runs.extend(github.get(f"/repos/{repository}/actions/runs?status=completed&per_page=1")["workflow_runs"]))
        if runs:
            step(repository, "read a run's jobs (Actions: read)",
                 lambda: github.get(f"/repos/{repository}/actions/runs/{runs[0]['id']}/jobs?per_page=1"))
            step(repository, "cancel a run (Actions: write)",
                 lambda: github.call("POST", f"/repos/{repository}/actions/runs/{runs[0]['id']}/cancel"), accept=(409,))
        step(repository, "read the activity log (Contents: read)",
             lambda: github.get(f"/repos/{repository}/activity?per_page=1"))
        step(repository, "read runners (Administration: read)",
             lambda: github.get(f"/repos/{repository}/actions/runners?per_page=1"))

        def runner():
            created = github.call("POST", f"/repos/{repository}/actions/runners/generate-jitconfig",
                                  {"name": f"{VM}-jit-check{secrets.token_hex(3)}", "runner_group_id": 1,
                                   "labels": list(LABELS), "work_folder": "_work"})
            github.call("DELETE", f"/repos/{repository}/actions/runners/{created['runner']['id']}")
        step(repository, "create and delete a one-job runner (Administration: write)", runner)
    print(f"token file {TOKEN_FILE}: {failures} failure(s) over {len(served)} served repositories")
    return 1 if failures else 0


def main(argv):
    if argv[:1] == ["run"]:
        run_forever()
    if argv[:1] == ["audit"]:
        return audit()
    if argv[:1] == ["check"]:
        return check()
    if argv[:1] == ["timings"] and len(argv) in (2, 3):
        return timings(argv[1], int(argv[2]) if len(argv) == 3 else 10)
    print(__doc__.split("Usage:", 1)[1], file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
