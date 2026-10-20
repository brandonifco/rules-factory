"""A private repository reaches a runner, or `onboard-check` says why not (decision 0084, #687).

`verify` is read-only and GitHub-only; `onboard` registers this host's runner, sets the routing and
verifies; both are held here with fakes for `GitHub` and the guest -- no test runs `factory-ci`,
`ssh`, `virsh` or a write against GitHub. The kit's lists (`LABELS`, `runners.json`, `register.sh`,
`factory-ci`, `RUNS_ON_LINE`) are held to one another.
"""
import base64
import contextlib
import importlib.util
import io
import json
import os
import re
import sys
import tempfile
import unittest
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.join(os.path.dirname(HERE), "ci-runner")
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("onboard_under_test", os.path.join(KIT, "onboard.py"))
onboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(onboard)
dispatch = onboard.dispatch

REPO = "brandonifco/engine"
NAME = "engine"
URL = f"https://github.com/{REPO}"
LABELS = ["self-hosted", "Linux", "X64", "factory-ci"]  # as GitHub spells the runner's labels
EXACT = json.dumps(list(dispatch.LABELS), separators=(",", ":"))
NOW = "2026-10-19T00:00:00Z"


def runner(name="factory-ci-1", rid=7, status="online", busy=False, labels=LABELS):
    return {"id": rid, "name": name, "status": status, "busy": busy, "labels": [{"name": n} for n in labels]}


def workflow(*jobs):
    """A workflow file: each job is (id, the full `runs-on` line or None, extra lines)."""
    text = "name: ci\non:\n  push:\njobs:\n"
    for job, line, extra in jobs:
        text += f"  {job}:\n" + (line + "\n" if line else "") + "    steps:\n      - run: true\n" + extra
    return text


GOOD = onboard.RUNS_ON_LINE
VALID = {"validate.yml": workflow(("validate", GOOD, ""))}


class FakeGitHub:
    """The REST API as `verify` and `onboard` ask it: reads by path, writes recorded."""

    def __init__(self, private=True, runners=(), variables=None, workflows=VALID, fail=None):
        self.private, self.runners = private, list(runners)
        self.variables = dict({"FACTORY_RUNS_ON": EXACT} if variables is None else variables)
        self.workflows, self.fail = workflows, dict(fail or {})
        self.posts, self.reads = [], []

    def refused(self, path):
        for part, code in self.fail.items():
            if part in path:
                raise urllib.error.HTTPError(path, code, "Forbidden" if code == 403 else "Not Found", {}, None)

    @staticmethod
    def page(items, path, size):
        assert f"per_page={size}" in path, path
        number = int(re.search(r"[?&]page=(\d+)", path).group(1))
        return items[(number - 1) * size:number * size]

    def get(self, path, cache=False):
        self.reads.append(path)
        self.refused(path)
        bare = path.split("?")[0]
        if bare == f"/repos/{REPO}":
            return {"private": self.private, "visibility": "private" if self.private else "public", "default_branch": "main"}
        if bare.endswith("/actions/runners"):
            return {"total_count": len(self.runners), "runners": self.page(self.runners, path, 100)}
        if bare.endswith("/actions/variables"):
            items = [{"name": k, "value": v} for k, v in self.variables.items()]
            return {"total_count": len(items), "variables": self.page(items, path, 30)}
        if bare.endswith("/contents/.github/workflows"):
            if self.workflows is None:
                raise urllib.error.HTTPError(path, 404, "Not Found", {}, None)
            return [{"type": "file", "path": f".github/workflows/{n}"} for n in sorted(self.workflows)] + \
                   [{"type": "dir", "path": ".github/workflows/sub"}]
        if "/contents/.github/workflows/" in bare:
            text = self.workflows[bare.rsplit("/", 1)[1]]
            return {"encoding": "base64", "content": base64.b64encode(text.encode()).decode()}
        raise AssertionError(path)

    def call(self, method, path, body=None, cache=False):
        self.posts.append((method, path, body))
        self.refused(path)
        if path.endswith("/registration-token"):
            return {"token": "T0KEN-SECRET"}
        if path.endswith("/actions/variables"):
            self.variables[body["name"]] = body["value"]
        elif "/actions/variables/" in path:
            self.variables[path.rsplit("/", 1)[1]] = body["value"]
        return None


class FakeGuest:
    """The guest as `onboard` asks it: what it holds, and a registration that GitHub then lists."""

    def __init__(self, github, held=None, vm="factory-ci-1", status="online", up=True):
        self.github, self.held, self.vm, self.status, self.up = github, dict(held or {}), vm, status, up
        self.calls, self.stdin = [], []

    def call(self, *args, stdin=None):
        self.calls.append(args)
        self.stdin.append(stdin)
        if not self.up:
            raise RuntimeError("ssh: connect to host 192.168.150.11 port 22: No route to host")
        if args[0] == "held":
            found = self.held.get(args[1])
            return json.dumps({"kind": "held", "account": f"fci-{args[1]}", "agentId": str(found[0]), "url": found[1]}) + "\n" if found else ""
        if args[0] == "register":
            name, repo = args[1], args[2]
            rid = 500 + len(self.calls)
            self.github.runners = [r for r in self.github.runners if r["name"] != self.vm] + [runner(self.vm, rid, self.status)]
            self.held[name] = (rid, f"https://github.com/{repo}")
            return ""
        raise AssertionError(args)

    def registered(self):
        return [c for c in self.calls if c[0] == "register"]


def verify(github, **kw):
    return onboard.verify(REPO, github, now=lambda: NOW, **kw)


class TestVerify(unittest.TestCase):
    def test_a_private_repository_with_an_online_runner_exact_routing_and_the_contract_line_passes(self):
        record = verify(FakeGitHub(runners=[runner()]))
        self.assertEqual([], record["findings"])
        self.assertEqual("pass", record["verdict"])
        self.assertEqual({"schema": "factory-ci/onboarding/1", "repository": REPO, "visibility": "private",
                          "checked_at": NOW}, {k: record[k] for k in ("schema", "repository", "visibility", "checked_at")})
        self.assertEqual([{"name": "factory-ci-1", "status": "online", "busy": False, "labels": LABELS, "authorized": True}],
                         record["runners"])
        self.assertEqual([{"path": ".github/workflows/validate.yml", "job": "validate", "runs_on": GOOD.strip()[len("runs-on: "):],
                           "ok": True}], record["workflows"])
        self.assertEqual(EXACT, record["routing"]["FACTORY_RUNS_ON"])
        json.dumps(record)

    def findings(self, github):
        record = verify(github)
        self.assertEqual("fail", record["verdict"])
        return "\n".join(record["findings"])

    def test_no_runner_fails(self):
        self.assertIn("no authorized runner is online with exactly factory-ci's labels", self.findings(FakeGitHub()))

    def test_a_runner_that_is_offline_fails(self):
        self.assertIn("no authorized runner is online", self.findings(FakeGitHub(runners=[runner(status="offline")])))

    def test_labels_must_be_exactly_factory_ci_s_and_case_is_not_compared(self):
        self.assertEqual("pass", verify(FakeGitHub(runners=[runner(labels=["SELF-HOSTED", "linux", "x64", "Factory-CI"])]))["verdict"])
        for labels in (LABELS + ["gpu"], LABELS[:3], ["self-hosted", "Linux", "X64"]):
            text = self.findings(FakeGitHub(runners=[runner(labels=labels)]))
            self.assertIn("not exactly self-hosted, linux, x64, factory-ci", text, labels)
            self.assertIn("no authorized runner is online", text, "a runner with other labels is not eligible")

    def test_a_runner_that_is_not_in_the_reviewed_list_fails_even_beside_a_good_one(self):
        text = self.findings(FakeGitHub(runners=[runner(), runner("laptop-ci", 9)]))
        self.assertIn("runner laptop-ci is not an authorized factory-ci runner", text)
        self.assertNotIn("runner factory-ci-1", text)

    def test_a_one_job_runner_is_authorized_only_as_a_listed_name_s(self):
        self.assertTrue(onboard.is_authorized("factory-ci-1-jit-0a1b2c3d"))
        self.assertTrue(onboard.is_authorized("factory-ci-2-jit-ff"))
        for name in ("factory-ci-3-jit-0a", "factory-ci-1-jit-", "factory-ci-1-jit-XYZ", "factory-ci-10", "xfactory-ci-1", None):
            self.assertFalse(onboard.is_authorized(name), name)

    def test_routing_missing_wrong_or_with_the_trusted_variable_fails_a_private_repository(self):
        self.assertIn("FACTORY_RUNS_ON is not set", self.findings(FakeGitHub(runners=[runner()], variables={})))
        for value in ('["ubuntu-24.04"]', '"ubuntu-24.04"', "not json", '["self-hosted","linux","x64"]', "[]"):
            self.assertIn("not exactly", self.findings(FakeGitHub(runners=[runner()], variables={"FACTORY_RUNS_ON": value})), value)
        self.assertEqual("pass", verify(FakeGitHub(runners=[runner()], variables={"FACTORY_RUNS_ON": '["Self-Hosted","LINUX","x64","factory-ci"]'}))["verdict"])
        text = self.findings(FakeGitHub(runners=[runner()], variables={"FACTORY_RUNS_ON": EXACT, "FACTORY_RUNS_ON_TRUSTED": EXACT}))
        self.assertIn("FACTORY_RUNS_ON_TRUSTED is set on a private repository", text)

    def test_a_literal_hosted_runs_on_is_a_silent_fallback_and_fails(self):
        for line in ("    runs-on: ubuntu-24.04", "    runs-on: [self-hosted, linux, x64, factory-ci]",
                     "    runs-on: ${{ vars.FACTORY_RUNS_ON || 'ubuntu-24.04' }}"):
            files = {"validate.yml": workflow(("validate", GOOD, ""), ("publish", line, ""))}
            record = verify(FakeGitHub(runners=[runner()], workflows=files))
            self.assertEqual("fail", record["verdict"], line)
            self.assertIn("validate.yml: job publish has runs-on", "\n".join(record["findings"]))
            self.assertEqual([True, False], [w["ok"] for w in record["workflows"]])

    def test_decision_0079s_line_is_accepted_on_a_private_repository_with_the_variable_exact_and_nowhere_else(self):
        self.assertEqual("    runs-on: ${{ fromJSON(vars.FACTORY_RUNS_ON || '\"ubuntu-24.04\"') }}", onboard.RUNS_ON_LINE_0079)
        old = {"validate.yml": workflow(("validate", onboard.RUNS_ON_LINE_0079, ""))}
        record = verify(FakeGitHub(runners=[runner()], workflows=old))
        self.assertEqual("pass", record["verdict"], record["findings"])
        self.assertEqual(["0079"], [w["ok"] for w in record["workflows"]])
        out = io.StringIO()
        onboard.report(record, out)
        self.assertIn("decision 0079's runner line", out.getvalue())
        # the variable missing: the routing check fails it, as it does for RUNS_ON_LINE
        text = self.findings(FakeGitHub(runners=[runner()], workflows=old, variables={}))
        self.assertIn("FACTORY_RUNS_ON is not set", text)
        # public: it would send a fork's run to the variable, so it stays a finding
        public = verify(FakeGitHub(private=False, variables={"FACTORY_RUNS_ON_TRUSTED": EXACT}, workflows=old))
        self.assertEqual("fail", public["verdict"])
        self.assertEqual([False], [w["ok"] for w in public["workflows"]])
        self.assertIn("not the contract line", "\n".join(public["findings"]))

    def test_the_ubuntu_latest_variant_of_0079s_line_stays_a_finding(self):
        line = "    runs-on: ${{ fromJSON(vars.FACTORY_RUNS_ON || '\"ubuntu-latest\"') }}"
        record = verify(FakeGitHub(runners=[runner()], workflows={"validate.yml": workflow(("validate", line, ""))}))
        self.assertEqual("fail", record["verdict"])
        self.assertEqual([False], [w["ok"] for w in record["workflows"]])

    def test_a_trailing_yaml_comment_is_not_part_of_the_runs_on(self):
        for comment in (" # Enabled 2026-10-12", " # As build-and-test", "  #no space after", " #"):
            files = {"validate.yml": workflow(("validate", GOOD + comment, ""), ("again", onboard.RUNS_ON_LINE_0079 + comment, ""))}
            record = verify(FakeGitHub(runners=[runner()], workflows=files))
            self.assertEqual("pass", record["verdict"], (comment, record["findings"]))
            self.assertEqual([True, "0079"], [w["ok"] for w in record["workflows"]])
            self.assertEqual(onboard.RUNS_ON_LINE.strip()[len("runs-on: "):], record["workflows"][0]["runs_on"])
        # a comment does not make a wrong line right
        files = {"validate.yml": workflow(("validate", "    runs-on: ubuntu-24.04 # " + GOOD.strip(), ""))}
        self.assertEqual("fail", verify(FakeGitHub(runners=[runner()], workflows=files))["verdict"])

    def test_a_hash_inside_quotes_or_not_after_whitespace_is_not_a_comment(self):
        self.assertEqual("'a # b' x", onboard.strip_comment("'a # b' x # c"))
        self.assertEqual('"a # b"', onboard.strip_comment('"a # b" # c'))
        self.assertEqual("${{ fromJSON('\"#x\"') }}", onboard.strip_comment("${{ fromJSON('\"#x\"') }} # c"))
        self.assertEqual("ubuntu#24", onboard.strip_comment("ubuntu#24"))
        self.assertEqual("", onboard.strip_comment("# only a comment"))
        line = "    runs-on: ${{ vars.FACTORY_RUNS_ON || '\"#ubuntu\"' }}"
        record = verify(FakeGitHub(runners=[runner()], workflows={"w.yml": workflow(("build", line, ""))}))
        self.assertEqual("fail", record["verdict"])
        self.assertIn("'\"#ubuntu\"'", record["workflows"][0]["runs_on"])

    def test_every_workflow_file_is_read_in_both_extensions_and_a_directory_is_not(self):
        files = {"a.yml": workflow(("one", GOOD, "")), "b.yaml": workflow(("two", "    runs-on: ubuntu-latest", "")),
                 "notes.txt": "runs-on: nothing"}
        record = verify(FakeGitHub(runners=[runner()], workflows=files))
        self.assertEqual([(".github/workflows/a.yml", "one"), (".github/workflows/b.yaml", "two")],
                         [(w["path"], w["job"]) for w in record["workflows"]])
        self.assertEqual("fail", record["verdict"])

    def test_a_reusable_workflow_job_without_runs_on_is_reported_not_failed(self):
        files = {"call.yml": "on: push\njobs:\n  call:\n    uses: ./.github/workflows/other.yml\n    with:\n      x: 1\n"}
        record = verify(FakeGitHub(runners=[runner()], workflows=files))
        self.assertEqual("pass", record["verdict"], record["findings"])
        self.assertEqual([None], [w["ok"] for w in record["workflows"]])
        self.assertEqual("./.github/workflows/other.yml", record["workflows"][0]["uses"])
        out = io.StringIO()
        onboard.report(record, out)
        self.assertIn("note .github/workflows/call.yml: job call uses ./.github/workflows/other.yml", out.getvalue())

    def test_a_job_the_scan_cannot_read_fails_rather_than_passes(self):
        for text in ("jobs:\n  build: {runs-on: ubuntu-24.04}\n",           # flow style
                     "jobs:\n  build:\n    runs-on:\n      group: big\n",     # block value
                     "jobs:\n  build:\n    steps: []\n",                       # names no runner at all
                     "name: only a name\n"):                                   # no jobs
            record = verify(FakeGitHub(runners=[runner()], workflows={"w.yml": text}))
            self.assertEqual("fail", record["verdict"], text)

    def test_text_that_only_looks_like_a_runs_on_is_not_one(self):
        deeper = workflow(("build", GOOD, "      - run: |\n          echo 'runs-on: ubuntu-24.04'\n"))
        commented = "jobs:\n  # runs-on: ubuntu-24.04\n  build:\n" + GOOD + "\n"
        for text in (deeper, commented):
            record = verify(FakeGitHub(runners=[runner()], workflows={"w.yml": text}))
            self.assertEqual("pass", record["verdict"], record["findings"])

    def test_no_workflow_at_all_fails(self):
        for files in (None, {}):
            text = self.findings(FakeGitHub(runners=[runner()], workflows=files))
            self.assertIn("no workflow on main", text)

    def test_two_hosts_are_accepted_and_either_alone_is_enough(self):
        both = verify(FakeGitHub(runners=[runner(), runner("factory-ci-2", 8)]))
        self.assertEqual(("pass", [True, True]), (both["verdict"], [r["authorized"] for r in both["runners"]]))
        self.assertEqual("pass", verify(FakeGitHub(runners=[runner("factory-ci-2", 8)]))["verdict"])
        self.assertEqual("pass", verify(FakeGitHub(runners=[runner(), runner("factory-ci-2", 8, "offline")]))["verdict"],
                         "one online authorized runner is enough")

    def test_a_public_repository_is_verified_by_the_dispatch_rules(self):
        trusted = {"FACTORY_RUNS_ON_TRUSTED": EXACT}
        record = verify(FakeGitHub(private=False, variables=trusted))
        self.assertEqual(("pass", "public", "dispatch"), (record["verdict"], record["visibility"], record["routing"]["mode"]), record["findings"])
        self.assertEqual("pass", verify(FakeGitHub(private=False, variables=trusted, runners=[runner("factory-ci-1-jit-0a1b", 3, "online")]))["verdict"],
                         "a one-job runner is the dispatcher's")
        cases = (("a standing runner", dict(runners=[runner()], variables=trusted), "public repository with a standing runner factory-ci-1"),
                 ("an unlisted one", dict(runners=[runner("laptop", 4)], variables=trusted), "runner laptop is not an authorized"),
                 ("FACTORY_RUNS_ON", dict(variables={**trusted, "FACTORY_RUNS_ON": EXACT}), "public repository with FACTORY_RUNS_ON set"),
                 ("trusted missing", dict(variables={}), "FACTORY_RUNS_ON_TRUSTED is not set"),
                 ("trusted wrong", dict(variables={"FACTORY_RUNS_ON_TRUSTED": '["ubuntu-24.04"]'}), "FACTORY_RUNS_ON_TRUSTED is '[\"ubuntu-24.04\"]', not exactly"))
        for what, kw, finding in cases:
            self.assertIn(finding, self.findings(FakeGitHub(private=False, **kw)), what)

    def test_a_public_repository_needs_no_runner_online(self):
        self.assertNotIn("no authorized runner", "\n".join(verify(FakeGitHub(private=False, variables={"FACTORY_RUNS_ON_TRUSTED": EXACT}))["findings"]))

    def test_lists_are_read_whole_across_pages(self):
        many = {f"V{i}": "x" for i in range(34)}
        many["FACTORY_RUNS_ON_TRUSTED"] = EXACT
        self.assertIn("FACTORY_RUNS_ON_TRUSTED is set", self.findings(FakeGitHub(runners=[runner()], variables={**many, "FACTORY_RUNS_ON": EXACT})),
                      "a variable past the first page of 30 is seen")
        crowd = [runner(f"factory-ci-1-jit-{i:04x}", 100 + i) for i in range(101)] + [runner()]
        record = verify(FakeGitHub(runners=crowd))
        self.assertEqual(102, len(record["runners"]))

    def test_the_record_is_the_same_when_nothing_changed(self):
        github = FakeGitHub(runners=[runner(), runner("factory-ci-2", 8)])
        self.assertEqual(verify(github), verify(github))


class TestADeliberatelyHostedJobIsDeclaredNotAssumed(unittest.TestCase):
    """Decision 0080 point 8: publication and manual maintenance stay on `ubuntu-24.04`. runners.json lists
    each such job by repository, workflow, job and exact runs-on; nothing else literal passes."""

    PUBLISH = "    runs-on: ubuntu-24.04"
    FILES = {"validate.yml": workflow(("validate", GOOD, "")), "publish.yml": workflow(("publish", PUBLISH, ""))}
    PATH = ".github/workflows/publish.yml"

    def item(self, **kw):
        return {"repository": REPO, "workflow": self.PATH, "job": "publish", "runs_on": "ubuntu-24.04",
                "reason": "0080 point 8: publication credentials", **kw}

    def public(self, files=None):
        return FakeGitHub(private=False, variables={"FACTORY_RUNS_ON_TRUSTED": EXACT}, workflows=files or self.FILES)

    def test_a_listed_job_of_a_public_repository_is_in_the_record_and_not_a_finding(self):
        record = verify(self.public(), hosted_jobs=[self.item()])
        self.assertEqual([], record["findings"])
        self.assertEqual("pass", record["verdict"])
        hosted = [w for w in record["workflows"] if w["job"] == "publish"][0]
        self.assertEqual(("hosted", "0080 point 8: publication credentials"), (hosted["ok"], hosted["hosted"]))
        self.assertEqual([True, "hosted"], [w["ok"] for w in sorted(record["workflows"], key=lambda w: w["job"] == "publish")])
        out = io.StringIO()
        onboard.report(record, out)
        self.assertIn("job publish stays on ubuntu-24.04 on purpose (0080 point 8: publication credentials", out.getvalue())
        json.dumps(record)

    def test_without_the_list_the_same_job_is_a_finding(self):
        record = verify(self.public(), hosted_jobs=[])
        self.assertEqual("fail", record["verdict"])
        self.assertIn("publish.yml: job publish has runs-on 'ubuntu-24.04'", "\n".join(record["findings"]))

    def test_a_listed_job_whose_runs_on_changed_is_a_finding(self):
        for line in ("    runs-on: ubuntu-latest", "    runs-on: ubuntu-22.04", '    runs-on: "ubuntu-24.04"',
                     "    runs-on: [self-hosted, linux, x64, factory-ci]", GOOD):
            files = dict(self.FILES, **{"publish.yml": workflow(("publish", line, ""))})
            record = verify(self.public(files), hosted_jobs=[self.item()])
            self.assertEqual("fail", record["verdict"], line)
            self.assertIn("as deliberately hosted", "\n".join(record["findings"]), line)
            self.assertIn("but it now has runs-on", "\n".join(record["findings"]), line)

    def test_a_literal_runs_on_that_is_not_listed_is_a_finding_beside_a_listed_one(self):
        files = dict(self.FILES, **{"publish.yml": workflow(("publish", self.PUBLISH, ""), ("validate", self.PUBLISH, ""))})
        record = verify(self.public(files), hosted_jobs=[self.item()])
        self.assertEqual("fail", record["verdict"])
        self.assertEqual(1, len(record["findings"]), record["findings"])
        self.assertIn("publish.yml: job validate has runs-on 'ubuntu-24.04'", record["findings"][0])
        self.assertEqual(["hosted", False], [w["ok"] for w in record["workflows"] if w["path"] == self.PATH])

    def test_the_same_job_name_in_another_workflow_or_repository_is_not_listed(self):
        files = dict(self.FILES, **{"other.yml": workflow(("publish", self.PUBLISH, ""))})
        record = verify(self.public(files), hosted_jobs=[self.item(), self.item(repository="brandonifco/elsewhere", workflow=".github/workflows/other.yml")])
        self.assertEqual("fail", record["verdict"])
        self.assertEqual(1, len(record["findings"]), record["findings"])
        self.assertIn("other.yml: job publish has runs-on", record["findings"][0])

    def test_a_listed_job_in_a_private_repository_is_a_finding_and_the_job_is_not_exempt(self):
        github = FakeGitHub(private=True, runners=[runner()], workflows=self.FILES)
        record = verify(github, hosted_jobs=[self.item()])
        text = "\n".join(record["findings"])
        self.assertEqual("fail", record["verdict"])
        self.assertIn(f"but {REPO} is private: only a public repository may have a hosted job", text)
        self.assertIn("publish.yml: job publish has runs-on 'ubuntu-24.04'", text)
        self.assertEqual([True, False], [w["ok"] for w in sorted(record["workflows"], key=lambda w: w["job"] == "publish")])

    def test_a_listed_job_that_no_longer_exists_is_a_finding(self):
        for files in ({"validate.yml": workflow(("validate", GOOD, ""))},                                 # the file is gone
                      {"validate.yml": workflow(("validate", GOOD, "")), "publish.yml": workflow(("release", self.PUBLISH, ""))}):
            record = verify(self.public(files), hosted_jobs=[self.item()])
            text = "\n".join(record["findings"])
            self.assertEqual("fail", record["verdict"])
            self.assertIn("there is no such job on main: remove the entry", text)

    def test_the_entry_is_matched_to_its_repository_whatever_the_case(self):
        record = verify(self.public(), hosted_jobs=[self.item(repository=REPO.upper())])
        self.assertEqual("pass", record["verdict"], record["findings"])

    def test_the_committed_list_is_read_when_no_list_is_given(self):
        with open(os.path.join(KIT, "runners.json"), encoding="utf-8") as handle:
            committed = json.load(handle)["hosted_jobs"]
        self.assertEqual(committed, onboard.load_hosted_jobs())
        record = onboard.verify("brandonifco/rules-factory", self.rules_factory(), now=lambda: NOW)
        self.assertEqual("pass", record["verdict"], record["findings"])

    def rules_factory(self):
        github = self.public({"publish-map.yml": workflow(("gate", self.PUBLISH, ""), ("publish", self.PUBLISH, "")),
                              "judge-rebuild.yml": workflow(("judge", self.PUBLISH, ""))})
        get = github.get
        github.get = lambda path, cache=False: get(path.replace("brandonifco/rules-factory", REPO), cache)
        return github


class TestAReadThatFailsIsAnErrorNeverAPass(unittest.TestCase):
    def check(self, fail):
        github = FakeGitHub(runners=[runner()], fail=fail)
        with self.assertRaises(onboard.Unreadable) as caught:
            verify(github)
        return str(caught.exception)

    def test_each_read_names_what_could_not_be_read_and_the_permission(self):
        for part, what, permission in (("/actions/runners", "the repository's runners", "Administration: read"),
                                       ("/actions/variables", "the repository's variables", "Variables"),
                                       ("/contents/.github/workflows/validate.yml", "workflow .github/workflows/validate.yml", "Contents: read"),
                                       ("/contents/.github/workflows?", "the workflow directory", "Contents: read")):
            fail = {part: 403}
            message = self.check(fail)
            self.assertIn(what, message, part)
            self.assertIn("HTTP 403", message)
            self.assertIn(permission, message)

    def test_the_repository_itself_unreadable_is_an_error(self):
        message = self.check({f"/repos/{REPO}?": 404, f"/repos/{REPO}": 404})
        self.assertIn("the repository", message)

    def test_a_network_error_or_a_garbled_answer_is_an_error_too(self):
        class Broken(FakeGitHub):
            def get(self, path, cache=False):
                if "/actions/runners" in path:
                    raise urllib.error.URLError("temporary failure in name resolution")
                return super().get(path)
        with self.assertRaises(onboard.Unreadable):
            verify(Broken(runners=[runner()]))

        class Garbled(FakeGitHub):
            def get(self, path, cache=False):
                return {"runners": "none"} if "/actions/runners" in path else super().get(path)
        with self.assertRaises(onboard.Unreadable):
            verify(Garbled())

    def test_a_list_too_long_to_read_whole_is_an_error(self):
        crowd = [runner(f"factory-ci-1-jit-{i:05x}", i) for i in range(1001)]
        with self.assertRaises(onboard.Unreadable) as caught:
            verify(FakeGitHub(runners=crowd))
        self.assertIn("whole", str(caught.exception))

    def test_check_exits_2_prints_the_reason_and_writes_no_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "onboarding.json")
            err = io.StringIO()
            original = onboard.github_client
            onboard.github_client = lambda: FakeGitHub(runners=[runner()], fail={"/actions/runners": 403})
            try:
                with contextlib.redirect_stderr(err):
                    code = onboard.main(["check", REPO, "--json", path])
            finally:
                onboard.github_client = original
            self.assertEqual(2, code)
            self.assertIn("could not read the repository's runners", err.getvalue())
            self.assertFalse(os.path.exists(path))


class TestCheckWritesTheEvidence(unittest.TestCase):
    def run_check(self, github, *extra):
        out = io.StringIO()
        original = onboard.github_client
        onboard.github_client = lambda: github
        try:
            with contextlib.redirect_stdout(out):
                return onboard.main(["check", REPO, *extra]), out.getvalue()
        finally:
            onboard.github_client = original

    def test_a_pass_exits_0_and_a_finding_exits_1_and_both_leave_the_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "onboarding.json")
            code, out = self.run_check(FakeGitHub(runners=[runner()]), "--json", path)
            self.assertEqual(0, code, out)
            self.assertIn(": pass, 0 finding(s)", out)
            with open(path, encoding="utf-8") as handle:
                self.assertEqual("pass", json.load(handle)["verdict"])
            code, out = self.run_check(FakeGitHub(variables={}), "--json", path)
            self.assertEqual(1, code)
            self.assertIn("  X   no authorized runner is online", out)
            with open(path, encoding="utf-8") as handle:
                record = json.load(handle)
            self.assertEqual(("fail", 2), (record["verdict"], len(record["findings"])))
            self.assertEqual([], [n for n in os.listdir(tmp) if n != "onboarding.json"], "no temporary file is left")

    def test_check_never_writes_to_github_or_the_guest(self):
        github = FakeGitHub()
        self.run_check(github)
        self.assertEqual([], github.posts)

    def test_a_missing_gh_login_fails_explicitly(self):
        original = dispatch.GitHub

        def no_login(*a, **k):
            raise FileNotFoundError(2, "No such file or directory: 'gh'")
        dispatch.GitHub = no_login
        try:
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = onboard.main(["check", REPO])
        finally:
            dispatch.GitHub = original
        self.assertEqual(2, code)
        self.assertIn("gh auth login", err.getvalue())
        self.assertIn("Administration", err.getvalue())


class TestOnboard(unittest.TestCase):
    def go(self, github, guest, vm="factory-ci-1", **kw):
        logged = []
        record = onboard.onboard(REPO, github, guest, vm, now=lambda: NOW, log=logged.append, **kw)
        return record, logged

    def writes(self, github):
        return [(m, p.split(f"/repos/{REPO}")[1]) for m, p, _ in github.posts]

    def test_a_repository_with_no_runner_is_registered_routed_and_verified(self):
        github = FakeGitHub(variables={})
        guest = FakeGuest(github)
        record, logged = self.go(github, guest)
        self.assertEqual(("pass", []), (record["verdict"], record["findings"]))
        self.assertEqual([("POST", "/actions/runners/registration-token"), ("POST", "/actions/variables")], self.writes(github))
        self.assertEqual({"name": "FACTORY_RUNS_ON", "value": EXACT}, github.posts[1][2])
        self.assertEqual([("register", NAME, REPO)], guest.registered())
        self.assertEqual("T0KEN-SECRET\n", guest.stdin[guest.calls.index(("register", NAME, REPO))], "the token goes on stdin")
        self.assertFalse(any("T0KEN" in str(arg) for call in guest.calls for arg in call), "and never in an argument")
        self.assertFalse(any("T0KEN" in json.dumps(record) or "T0KEN" in line for line in logged))

    def test_already_registered_and_held_makes_no_registration_and_the_record_is_the_same_twice(self):
        github = FakeGitHub(runners=[runner(rid=7)])
        guest = FakeGuest(github, held={NAME: (7, URL)})
        first, logged = self.go(github, guest)
        second, _ = self.go(github, guest)
        self.assertEqual("pass", first["verdict"])
        self.assertEqual(first, second)
        self.assertEqual([], github.posts, "no token, no variable: nothing was written")
        self.assertEqual([], guest.registered())
        self.assertIn("already registered", logged[0])

    def test_a_same_named_runner_this_guest_does_not_hold_is_refused_and_never_replaced(self):
        for held in ({}, {NAME: (99, URL)}):
            github = FakeGitHub(runners=[runner(rid=7)], variables={})
            guest = FakeGuest(github, held=held)
            with self.assertRaises(onboard.Refused) as caught:
                self.go(github, guest)
            self.assertIn("does not hold", str(caught.exception))
            self.assertIn("not replacing", str(caught.exception))
            self.assertEqual([], github.posts, "no registration token was even asked for")
            self.assertEqual([], guest.registered())
            self.assertEqual([7], [r["id"] for r in github.runners])

    def test_an_account_registered_for_another_repository_is_not_taken_over(self):
        github = FakeGitHub()
        guest = FakeGuest(github, held={NAME: (7, "https://github.com/someone-else/engine")})
        with self.assertRaises(onboard.Refused) as caught:
            self.go(github, guest)
        self.assertIn("someone-else/engine", str(caught.exception))
        self.assertEqual([], github.posts)

    def test_a_registration_this_guest_holds_that_went_offline_or_wrong_is_registered_again(self):
        for bad in (runner(status="offline"), runner(labels=LABELS + ["extra"])):
            github = FakeGitHub(runners=[bad])
            guest = FakeGuest(github, held={NAME: (7, URL)})
            record, _ = self.go(github, guest)
            self.assertEqual("pass", record["verdict"], record["findings"])
            self.assertEqual([("register", NAME, REPO)], guest.registered())

    def test_the_variable_is_set_only_when_it_is_not_exact(self):
        for variables, expect in (({}, [("POST", "/actions/variables")]),
                                  ({"FACTORY_RUNS_ON": '["ubuntu-24.04"]'}, [("PATCH", "/actions/variables/FACTORY_RUNS_ON")]),
                                  ({"FACTORY_RUNS_ON": "garbage"}, [("PATCH", "/actions/variables/FACTORY_RUNS_ON")]),
                                  ({"FACTORY_RUNS_ON": '["Self-Hosted","Linux","X64","factory-ci"]'}, [])):
            github = FakeGitHub(runners=[runner()], variables=variables)
            self.go(github, FakeGuest(github, held={NAME: (7, URL)}))
            self.assertEqual(expect, self.writes(github), variables)
            self.assertTrue(onboard.exact(json.loads(github.variables["FACTORY_RUNS_ON"])))

    def test_a_two_host_repository_keeps_the_other_hosts_runner_untouched(self):
        other = runner("factory-ci-2", 8)
        github = FakeGitHub(runners=[other, runner(rid=7)])
        guest = FakeGuest(github, held={NAME: (7, URL)})
        record, _ = self.go(github, guest)
        self.assertEqual(("pass", ["factory-ci-1", "factory-ci-2"]), (record["verdict"], [r["name"] for r in record["runners"]]))
        self.assertEqual([], github.posts)
        # registering this host beside it: the office runner stays, the home one is added
        github = FakeGitHub(runners=[other], variables={})
        guest = FakeGuest(github)
        record, _ = self.go(github, guest)
        self.assertEqual("pass", record["verdict"], record["findings"])
        self.assertIn(other, github.runners)
        self.assertEqual(["factory-ci-1", "factory-ci-2"], sorted(r["name"] for r in github.runners))
        self.assertFalse([p for m, p, _ in github.posts if m == "DELETE" or "/8" in p])

    def test_a_single_host_repository_passes_on_its_own(self):
        github = FakeGitHub(runners=[runner()])
        self.assertEqual("pass", self.go(github, FakeGuest(github, held={NAME: (7, URL)}))[0]["verdict"])

    def test_the_other_host_registers_its_own_name(self):
        github = FakeGitHub(runners=[runner()], variables={})
        guest = FakeGuest(github, vm="factory-ci-2", held={})
        record, _ = self.go(github, guest, vm="factory-ci-2")
        self.assertEqual("pass", record["verdict"], record["findings"])
        self.assertEqual({"factory-ci-1", "factory-ci-2"}, {r["name"] for r in github.runners})

    def test_a_public_repository_is_refused_with_the_commands_to_use_and_nothing_is_touched(self):
        github = FakeGitHub(private=False, variables={})
        guest = FakeGuest(github)
        with self.assertRaises(onboard.Refused) as caught:
            self.go(github, guest)
        message = str(caught.exception)
        self.assertIn(f"factory-ci trust {REPO}", message)
        self.assertIn(f"factory-ci enable {REPO}", message)
        self.assertEqual(([], []), (github.posts, guest.calls))
        err = io.StringIO()
        original = (onboard.github_client, dispatch.Guest)
        onboard.github_client, dispatch.Guest = (lambda: github), (lambda: guest)
        try:
            with contextlib.redirect_stderr(err):
                self.assertEqual(1, onboard.main(["onboard", REPO]))
        finally:
            onboard.github_client, dispatch.Guest = original
        self.assertIn("is public", err.getvalue())

    def test_a_vm_that_is_not_in_the_reviewed_list_registers_nothing(self):
        github = FakeGitHub()
        with self.assertRaises(onboard.Refused):
            self.go(github, FakeGuest(github, vm="laptop"), vm="laptop")
        self.assertEqual([], github.posts)

    def test_a_refused_api_call_names_the_missing_permission(self):
        class WriteRefused(FakeGitHub):
            def call(self, method, path, body=None, cache=False):
                raise urllib.error.HTTPError(path, 403, "Forbidden", {}, None)
        for held, permission in (({}, "Administration: write"), ({NAME: (7, URL)}, "Variables")):
            github = WriteRefused(runners=[runner()] if held else [], variables={})
            with self.assertRaises(onboard.Failed) as caught:
                self.go(github, FakeGuest(github, held=held))
            self.assertIn(permission, str(caught.exception))
            self.assertIn("HTTP 403", str(caught.exception))

    def test_an_unreachable_guest_fails_explicitly_and_writes_nothing(self):
        github = FakeGitHub(variables={})
        guest = FakeGuest(github, up=False)
        with self.assertRaises(onboard.Failed) as caught:
            self.go(github, guest)
        self.assertIn("the guest could not be asked `held`", str(caught.exception))
        self.assertIn("factory-ci status", str(caught.exception))
        self.assertEqual([], github.posts)

    def test_a_runner_that_takes_a_moment_to_come_online_is_waited_for_only_after_a_change(self):
        github = FakeGitHub(variables={})
        guest = FakeGuest(github, status="offline")
        slept = []

        def sleep(seconds):
            slept.append(seconds)
            github.runners = [dict(r, status="online") for r in github.runners]
        record, _ = self.go(github, guest, wait=30, sleep=sleep, interval=3)
        self.assertEqual(("pass", [3]), (record["verdict"], slept))
        # nothing changed and it fails: no waiting, the verdict is reported at once
        github = FakeGitHub(runners=[runner()], variables={"FACTORY_RUNS_ON": EXACT, "FACTORY_RUNS_ON_TRUSTED": EXACT})
        slept.clear()
        record, _ = self.go(github, FakeGuest(github, held={NAME: (7, URL)}), wait=30, sleep=slept.append)
        self.assertEqual(("fail", []), (record["verdict"], slept))

    def test_the_guard_checks_what_register_must_not_replace(self):
        github = FakeGitHub(runners=[runner(rid=7)])
        with self.assertRaises(onboard.Refused):
            onboard.plan(REPO, github, FakeGuest(github), "factory-ci-1")
        self.assertEqual(7, onboard.plan(REPO, github, FakeGuest(github, held={NAME: (7, URL)}), "factory-ci-1")["id"])
        self.assertIsNone(onboard.plan(REPO, FakeGitHub(), FakeGuest(FakeGitHub()), "factory-ci-1"))


class TestTheKitAgreesWithItself(unittest.TestCase):
    """`LABELS`, `runners.json`, `register.sh`, `factory-ci` and the workflow line are one contract."""

    def read(self, *parts):
        with open(os.path.join(KIT, *parts), encoding="utf-8") as handle:
            return handle.read()

    def test_runners_json_lists_the_two_hosts_with_exactly_the_labels(self):
        document = json.loads(self.read("runners.json"))
        self.assertEqual("factory-ci/runners/1", document["schema"])
        self.assertEqual([("factory-ci-1", "home"), ("factory-ci-2", "office")], [(r["name"], r["site"]) for r in document["runners"]])
        for entry in document["runners"]:
            self.assertEqual(sorted(dispatch.LABELS), sorted(label.casefold() for label in entry["labels"]), entry["name"])
            self.assertTrue(onboard.exact(entry["labels"]))

    def test_runners_json_declares_hosted_jobs_only_as_publication_or_manual_maintenance_in_public_repositories(self):
        jobs = json.loads(self.read("runners.json"))["hosted_jobs"]
        self.assertTrue(jobs)
        keys = [(j["repository"], j["workflow"], j["job"]) for j in jobs]
        self.assertEqual(len(keys), len(set(keys)), "an entry is listed once")
        for job in jobs:
            self.assertEqual({"repository", "workflow", "job", "runs_on", "reason"}, set(job), job)
            self.assertEqual("ubuntu-24.04", job["runs_on"])
            self.assertIn(job["reason"], ("0080 point 8: publication credentials", "manual maintenance"))
            self.assertRegex(job["workflow"], r"^\.github/workflows/[^/]+\.ya?ml$")
        self.assertEqual({"brandonifco/rules-factory", "brandonifco/faa-part-107", "brandonifco/rules-kernel"},
                         {j["repository"] for j in jobs})  # public repositories the dispatcher serves; no private one

    def test_register_sh_registers_exactly_those_labels(self):
        script = self.read("guest", "register.sh")
        custom = re.search(r'labels="\$\{3:-([^}]*)\}"', script).group(1)
        defaults = re.search(r"\(labels: ([^$]*)\$labels\)", script).group(1)
        registered = [part.strip() for part in (defaults + custom).split(",") if part.strip()]
        self.assertEqual(sorted(dispatch.LABELS), sorted(label.casefold() for label in registered))
        self.assertTrue(onboard.exact(registered))
        self.assertIn("--labels \"$labels\"", script)

    def test_factory_ci_enables_exactly_those_labels(self):
        script = self.read("factory-ci")
        self.assertEqual(list(dispatch.LABELS), json.loads(re.search(r"^LABELS='([^']*)'", script, re.M).group(1)))

    def test_the_contract_line_is_the_one_the_recipes_carry(self):
        sys.path.insert(0, os.path.join(os.path.dirname(HERE), "factory"))
        import repository
        self.assertEqual(repository.RUNS_ON_LINE, onboard.RUNS_ON_LINE)
        self.assertEqual(repository.RUNS_ON_VARIABLE, onboard.RUNS_ON_VARIABLE)
        self.assertEqual(repository.RUNS_ON_TRUSTED_VARIABLE, onboard.TRUSTED_VARIABLE)

    def test_factory_ci_has_the_commands_and_register_asks_before_it_replaces(self):
        script = self.read("factory-ci")
        self.assertIn("cmd_onboard() {", script)
        self.assertIn("cmd_onboard_check() {", script)
        register = script[script.index("cmd_register() {"):script.index("cmd_deregister() {")]
        self.assertLess(register.index('onboard_py guard "$repo"'), register.index("registration-token"),
                        "the same-name check comes before a token is even asked for")
        self.assertIn("--replace", self.read("guest", "register.sh"), "the guest's own re-registration is unchanged")
        self.assertNotIn("--replace", self.read("onboard.py").replace("never --replace", "").replace("not replacing", ""),
                         "onboard.py never passes --replace to anything")

    def test_the_guest_answers_held_and_register_and_the_host_never_sends_it_shell(self):
        guest = self.read("guest", "dispatch-guest.sh")
        self.assertIn("inventory|held|register) ", guest)
        self.assertIn("exec /opt/factory-ci/bin/register", guest)
        for arg in ("$(id)", "a b", "a;b"):
            with self.assertRaises(ValueError):
                dispatch.Guest.call("held", arg)

    def test_the_gh_reader_cannot_write(self):
        self.assertFalse(hasattr(onboard.GhApi, "call"))


if __name__ == "__main__":
    unittest.main()
