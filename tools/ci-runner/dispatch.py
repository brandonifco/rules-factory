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
     job-started hook requires before a job's first step, and starts one one-job (JIT) runner per
     admitted queued job, with exactly factory-ci's labels, as that repository's own account.
  4. It deletes a one-job runner left idle, stops a guest runner GitHub no longer knows, and has
     the guest reap finished ones.

The two job slots in the guest still bound how many jobs run at once; a one-job runner adds no
capacity. `judge` is pure and is what the tests hold; everything else is I/O around it.

Usage:
  dispatch.py run                      the dispatcher loop (factory-ci dispatch; a user service)
  dispatch.py audit                    the boundary as one: registrations, visibility, variables,
                                       fork approval; exit 1 on any finding (factory-ci audit)
  dispatch.py timings OWNER/REPO [N]   queue and run time of the last N runs' jobs, by runner
Standard library only.
"""
import json
import os
import secrets
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

KIT = os.path.dirname(os.path.abspath(__file__))
FACTORY_CI = os.path.join(KIT, "factory-ci")
VM = os.environ.get("FACTORY_CI_VM", "factory-ci-1")
LABELS = ("self-hosted", "linux", "x64", "factory-ci")
POLL = float(os.environ.get("FACTORY_CI_DISPATCH_POLL", "10"))
JIT_MAX = int(os.environ.get("FACTORY_CI_JIT_MAX", "4"))
IDLE_MAX = 300
STARTING = 120
PENDING_GRACE = 120
API = "https://api.github.com"

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

def log(message):
    print(f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ} {message}", flush=True)


class GitHub:
    """The REST API as the owner. List reads are conditional: GitHub does not count a 304."""

    def __init__(self):
        self.token = self._token()
        self.etags = {}

    @staticmethod
    def _token():
        return subprocess.run(["gh", "auth", "token"], check=True, capture_output=True, text=True).stdout.strip()

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
                    if cache and response.headers.get("ETag"):
                        self.etags[url] = (response.headers["ETag"], value)
                    return value
            except urllib.error.HTTPError as error:
                if error.code == 304 and cache:
                    return self.etags[url][1]
                if error.code == 401 and attempt == 1:
                    self.token = self._token()
                    continue
                raise

    def get(self, path, cache=False):
        return self.call("GET", path, cache=cache)


class Guest:
    """The guest's half, `dispatch-guest`, through the kit's own `factory-ci ssh`."""

    @staticmethod
    def call(*args, stdin=None):
        command = "sudo /opt/factory-ci/bin/dispatch-guest " + " ".join(args)
        result = subprocess.run([FACTORY_CI, "ssh", command], input=stdin, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"guest {args[0]}: {result.stderr.strip() or result.stdout.strip()}")
        return result.stdout

    def inventory(self):
        """{"dispatch": {account: repo}, "persistent": {account: url}, "jit": {runner id: (account, state)}}"""
        found = {"dispatch": {}, "persistent": {}, "jit": {}}
        for line in self.call("inventory").splitlines():
            parts = line.split()
            if len(parts) == 3 and parts[0] in ("dispatch", "persistent"):
                found[parts[0]][parts[1]] = parts[2]
            elif len(parts) == 4 and parts[0] == "jit":
                found["jit"][int(parts[1])] = (parts[2], parts[3])
        return found


class Dispatcher:
    def __init__(self, github=None, guest=None):
        self.github = github or GitHub()
        self.guest = guest or Guest()
        self.verdicts = {}      # (repository, run id, attempt) -> (verdict, why, first seen)
        self.cancelled = set()  # run ids asked to cancel
        self.spawned = {}       # runner id -> (repository, account, monotonic time started)
        self.seen = set()       # runner ids this program started that GitHub has listed
        self.idle_since = {}    # runner id -> monotonic time first seen online and idle
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
        for status in ("queued", "in_progress", "waiting"):
            page = self.github.get(f"/repos/{repository}/actions/runs?status={status}&per_page=50", cache=True)
            for run in page.get("workflow_runs", []):
                runs[run["id"]] = run
        found = []
        for run in runs.values():
            jobs = self.github.get(f"/repos/{repository}/actions/runs/{run['id']}/attempts/{run['run_attempt']}/jobs?per_page=100",
                                   cache=True)
            for job in jobs.get("jobs", []):
                if job.get("status") not in ("completed", "in_progress") and ours(job.get("labels")):
                    found.append((run, job))
        return found

    def verdict(self, repository, run):
        key = (repository, run["id"], run["run_attempt"])
        held = self.verdicts.get(key)
        if held and held[0] != "pending":
            return held[0], held[1]
        activity = None
        branch = branch_of(run)
        if branch and (run.get("head_repository") or {}).get("full_name", "").casefold() == repository.casefold():
            activity = []
            for page in (1, 2, 3):
                chunk = self.github.get(f"/repos/{repository}/activity?ref=refs/heads/{branch}&per_page=100&page={page}")
                activity.extend(chunk)
                if len(chunk) < 100 or any(item.get("after") == run.get("head_sha") for item in chunk):
                    break
        verdict, why = judge(repository, run, activity)
        first = held[2] if held else time.monotonic()
        if verdict == "pending" and time.monotonic() - first > PENDING_GRACE:
            verdict, why = "refuse", why + f", still after {PENDING_GRACE}s"
        if verdict != "pending" or not held:
            log(f"{repository} run {run['id']} attempt {run['run_attempt']} ({run.get('name')}): {verdict}: {why}")
        self.verdicts[key] = (verdict, why, first)
        return verdict, why

    def serve(self, account, repository, live):
        """Judge every job in `repository` a factory-ci runner could take, and start runners for the
        admitted queued ones; returns how many runners it started."""
        runners = self.github.get(f"/repos/{repository}/actions/runners?per_page=100", cache=True).get("runners", [])
        foreign = [r["name"] for r in runners if not r["name"].startswith(f"{VM}-jit-")]
        if foreign:
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
            if verdict == "refuse" and run["id"] not in self.cancelled:
                self.cancelled.add(run["id"])
                try:
                    self.github.call("POST", f"/repos/{repository}/actions/runs/{run['id']}/cancel")
                    log(f"{repository} run {run['id']}: cancelled; it asked for factory-ci and was not admitted")
                except urllib.error.HTTPError as error:
                    log(f"{repository} run {run['id']}: cancel failed: HTTP {error.code}")
        now = time.monotonic()
        mine = {r["id"]: r for r in runners if r["name"].startswith(f"{VM}-jit-")}
        running = {runner_id for runner_id, (owner, state) in self.inventory["jit"].items()
                   if owner == account and state == "active"}
        self.seen |= set(mine) & set(self.spawned)
        # A runner can take a job if it is idle, or still connecting with its guest unit up. One this
        # program started that GitHub has not listed yet counts until it is seen or STARTING passes;
        # once seen and gone, it ran its one job.
        supply = 0
        for runner_id, runner in mine.items():
            if runner.get("busy"):
                self.idle_since.pop(runner_id, None)
            elif runner.get("status") == "online":
                supply += 1
                self.idle_since.setdefault(runner_id, now)
            elif runner_id in running:
                supply += 1
        supply += sum(1 for runner_id, (repo, _, started) in self.spawned.items()
                      if repo == repository and runner_id not in mine and runner_id not in self.seen
                      and now - started < STARTING)
        for runner_id in [r for r in self.idle_since if r in mine and demand == 0 and now - self.idle_since[r] > IDLE_MAX]:
            self.retire(repository, runner_id, f"idle for {IDLE_MAX}s with nothing admitted to run")
        if blocked:
            if demand:
                log(f"{repository}: {demand} admitted job(s) wait: no runner starts while a job that was not admitted is unfinished")
            return 0
        wanted = min(demand - supply, JIT_MAX - live)
        if wanted <= 0:
            return 0
        # Every admitted run with a queued job is written before any runner starts: GitHub hands a
        # runner whichever matching job it likes, and the guest refuses a run not written here.
        self.guest.call("admit", account.removeprefix("fci-"), *sorted(admitted))
        for _ in range(wanted):
            self.spawn(account, repository)
        return wanted

    def spawn(self, account, repository):
        name = f"{VM}-jit-{secrets.token_hex(4)}"
        created = self.github.call("POST", f"/repos/{repository}/actions/runners/generate-jitconfig",
                                   {"name": name, "runner_group_id": 1, "labels": list(LABELS), "work_folder": "_work"})
        runner_id = created["runner"]["id"]
        try:
            self.guest.call("start", account.removeprefix("fci-"), str(runner_id), stdin=created["encoded_jit_config"] + "\n")
        except Exception:
            self.github.call("DELETE", f"/repos/{repository}/actions/runners/{runner_id}")
            raise
        self.spawned[runner_id] = (repository, account, time.monotonic())
        log(f"{repository}: started one-job runner {name} (id {runner_id}) as {account}")

    def retire(self, repository, runner_id, why):
        try:
            self.github.call("DELETE", f"/repos/{repository}/actions/runners/{runner_id}")
        except urllib.error.HTTPError as error:
            if error.code != 404:
                log(f"{repository}: could not delete runner {runner_id}: HTTP {error.code}")
                return
        self.guest.call("stop", str(runner_id))
        self.spawned.pop(runner_id, None)
        self.idle_since.pop(runner_id, None)
        log(f"{repository}: retired one-job runner {runner_id} ({why})")

    def reconcile(self):
        """A guest runner GitHub no longer knows is stopped; a finished one is reaped."""
        now = time.monotonic()
        known = set()
        for account, repository in self.inventory["dispatch"].items():
            runners = self.github.get(f"/repos/{repository}/actions/runners?per_page=100", cache=True).get("runners", [])
            known |= {r["id"] for r in runners}
            for r in runners:
                if r["name"].startswith(f"{VM}-jit-") and r["id"] not in self.inventory["jit"] \
                        and now - self.spawned.get(r["id"], (0, 0, 0))[2] > STARTING and r.get("status") != "online":
                    self.retire(repository, r["id"], "no guest runner")
        for runner_id, (account, state) in self.inventory["jit"].items():
            if state == "active" and runner_id not in known and now - self.spawned.get(runner_id, (0, 0, 0))[2] > STARTING:
                self.guest.call("stop", str(runner_id))
                log(f"{account}: stopped guest runner {runner_id}, which GitHub no longer knows")
        if any(state != "active" for _, state in self.inventory["jit"].values()):
            self.guest.call("reap")
        for runner_id in [r for r, (_, _, t) in self.spawned.items() if now - t > 8 * 3600]:
            self.spawned.pop(runner_id, None)
            self.seen.discard(runner_id)

    def cycle(self):
        self.refresh()
        live = sum(1 for _, state in self.inventory["jit"].values() if state == "active")
        for account, repository in sorted(self.inventory["dispatch"].items()):
            try:
                live += self.serve(account, repository, live)
            except (urllib.error.URLError, RuntimeError, KeyError, ValueError) as error:
                log(f"{repository}: this cycle failed: {error}")
        self.reconcile()


def run_forever():
    dispatcher = Dispatcher()
    log(f"dispatcher up: VM {VM}, labels {','.join(LABELS)}, poll {POLL}s, at most {JIT_MAX} one-job runners")
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
    for account, repository in sorted(inventory["dispatch"].items()):
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
        notes.append(f"{repository}: dispatch ({account}), FACTORY_RUNS_ON_TRUSTED {'set' if trusted else 'unset'}, fork approval {policy}")
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
            if not job.get("started_at") or not job.get("completed_at"):
                continue
            created, started, done = (datetime.fromisoformat(job[k].replace("Z", "+00:00")) for k in ("created_at", "started_at", "completed_at"))
            queue, took = (started - created).total_seconds(), (done - started).total_seconds()
            runner = job.get("runner_name") or "-"
            kind = "factory-ci" if runner.startswith(VM) else "hosted"
            print(f"{run['id']:>12} {(run['name'] + '/' + job['name'])[:38]:<38} {runner[:26]:<26} {queue:>5.0f}s {took:>5.0f}s {job.get('conclusion')}")
            groups.setdefault((run["name"], job["name"], kind), []).append((queue, took))
    print()
    for (workflow, job, kind), values in sorted(groups.items()):
        print(f"median {workflow}/{job} on {kind}: queue {statistics.median(v[0] for v in values):.0f}s, "
              f"run {statistics.median(v[1] for v in values):.0f}s over {len(values)} job(s)")
    return 0


def main(argv):
    if argv[:1] == ["run"]:
        run_forever()
    if argv[:1] == ["audit"]:
        return audit()
    if argv[:1] == ["timings"] and len(argv) in (2, 3):
        return timings(argv[1], int(argv[2]) if len(argv) == 3 else 10)
    print(__doc__.split("Usage:", 1)[1], file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
