"""The trusted dispatcher's boundary (decision 0080), as security regression tests.

`judge` decides whether a run may have a factory-ci runner; `ours` decides which jobs a factory-ci
runner could be handed at all; `Dispatcher.serve` starts runners only for admitted runs and none
while anything else is waiting. Each refusal here names the way a fork, a bot or an edited workflow
would otherwise reach the owner's machine.
"""
import importlib.util
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(os.path.dirname(HERE), "ci-runner", "dispatch.py")
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("dispatch", PATH)
dispatch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dispatch)

OWNER = "brandonifco"
REPO = f"{OWNER}/rules-factory"
SHA = "a" * 40


def run(event="push", actor=OWNER, triggering=None, head=REPO, sha=SHA, branch="main", repo=REPO, run_id=1, attempt=1):
    return {"id": run_id, "run_attempt": attempt, "name": "validate", "event": event, "head_sha": sha,
            "head_branch": branch, "actor": {"login": actor}, "triggering_actor": {"login": triggering or actor},
            "repository": {"full_name": repo, "default_branch": "main"},
            "head_repository": {"full_name": head} if head else None}


def placed(actor=OWNER, sha=SHA, ref="refs/heads/main", kind="push"):
    return {"after": sha, "actor": {"login": actor}, "ref": ref, "activity_type": kind}


class TestJudge(unittest.TestCase):
    def verdict(self, the_run, activity=(placed(),)):
        return dispatch.judge(REPO, the_run, None if activity is None else list(activity))[0]

    def test_the_owner_s_push_whose_commit_the_owner_put_there_is_admitted(self):
        self.assertEqual("admit", self.verdict(run()))

    def test_the_owner_s_pull_request_from_a_branch_here_is_admitted(self):
        self.assertEqual("admit", self.verdict(run(event="pull_request", branch="topic"),
                                                [placed(ref="refs/heads/topic", kind="branch_creation")]))

    def test_a_merge_the_owner_made_is_a_placement(self):
        self.assertEqual("admit", self.verdict(run(), [placed(kind="pr_merge")]))

    def test_a_status_run_with_no_branch_is_the_default_branch_s(self):
        self.assertEqual("admit", self.verdict(run(event="status", branch=None)))

    def test_owner_names_are_compared_as_github_compares_them(self):
        self.assertEqual("admit", self.verdict(run(actor="BrandonIFCO", triggering="BRANDONIFCO"), [placed(actor="BrandonIfco")]))

    def test_a_fork_s_code_is_refused_whoever_started_it(self):
        for actor in ("outsider", OWNER):
            self.assertEqual("refuse", self.verdict(run(event="pull_request", actor=actor, head="outsider/rules-factory")))

    def test_a_pull_request_whose_head_repository_was_deleted_is_refused(self):
        self.assertEqual("refuse", self.verdict(run(event="pull_request", head=None)))

    def test_another_repository_s_run_is_refused(self):
        self.assertEqual("refuse", self.verdict(run(repo=f"{OWNER}/other", head=f"{OWNER}/other")))

    def test_events_that_run_trusted_workflows_for_somebody_else_are_refused(self):
        for event in ("pull_request_target", "workflow_run", "issue_comment", "pull_request_review",
                      "pull_request_review_comment", "discussion", "create", "repository_dispatch", "", None):
            self.assertEqual("refuse", self.verdict(run(event=event)), event)

    def test_a_bot_s_run_is_refused(self):
        self.assertEqual("refuse", self.verdict(run(actor="dependabot[bot]"), [placed(actor="dependabot[bot]")]))

    def test_the_owner_re_running_a_bot_s_run_is_refused(self):
        self.assertEqual("refuse", self.verdict(run(actor="dependabot[bot]", triggering=OWNER)))

    def test_a_workflow_re_running_the_owner_s_run_is_refused(self):
        self.assertEqual("refuse", self.verdict(run(triggering="github-actions[bot]")))

    def test_a_commit_only_somebody_else_put_on_the_branch_is_refused(self):
        self.assertEqual("refuse", self.verdict(run(), [placed(actor="dependabot[bot]")]))

    def test_a_placement_on_another_branch_does_not_count(self):
        self.assertEqual("pending", self.verdict(run(), [placed(ref="refs/heads/elsewhere")]))

    def test_a_deletion_is_not_a_placement(self):
        self.assertEqual("pending", self.verdict(run(), [placed(kind="branch_deletion")]))

    def test_a_commit_nobody_is_recorded_placing_is_pending_not_admitted(self):
        self.assertEqual("pending", self.verdict(run(), []))
        self.assertEqual("pending", self.verdict(run(), None))

    def test_a_head_that_is_not_a_full_commit_id_is_refused(self):
        for sha in ("", "abc", "A" * 40, "g" * 40, "a" * 39):
            self.assertEqual("refuse", self.verdict(run(sha=sha), [placed(sha=sha)]), sha)

    def test_a_run_on_no_branch_is_refused(self):
        self.assertEqual("refuse", self.verdict(run(event="workflow_dispatch", branch=None)))


class TestOurs(unittest.TestCase):
    def test_a_job_is_ours_when_a_factory_ci_runner_s_labels_include_all_it_asks_for(self):
        for labels in (["self-hosted", "linux", "x64", "factory-ci"], ["self-hosted"], ["factory-ci"],
                       ["Self-Hosted", "Linux", "X64"], ["linux", "factory-ci"]):
            self.assertTrue(dispatch.ours(labels), labels)

    def test_a_hosted_job_or_a_label_factory_ci_lacks_is_not(self):
        for labels in (["ubuntu-24.04"], ["self-hosted", "gpu"], [], None, ["windows"]):
            self.assertFalse(dispatch.ours(labels), labels)


class FakeGitHub:
    def __init__(self, runs, jobs, activity, runners=()):
        self.runs, self.jobs, self.activity, self.runners = runs, jobs, activity, list(runners)
        self.posts, self.next_id = [], 100

    def get(self, path, cache=False):
        if "/actions/runs?status=" in path:
            status = path.split("status=")[1].split("&")[0]
            return {"workflow_runs": [r for r in self.runs if r.get("status", "queued") == status]}
        if "/jobs" in path:
            run_id = int(path.split("/actions/runs/")[1].split("/")[0])
            return {"jobs": self.jobs.get(run_id, [])}
        if "/activity" in path:
            return self.activity if "page=1" in path else []
        if path.endswith("/actions/runners?per_page=100"):
            return {"runners": self.runners}
        raise AssertionError(path)

    def call(self, method, path, body=None, cache=False):
        self.posts.append((method, path))
        if path.endswith("generate-jitconfig"):
            self.next_id += 1
            return {"runner": {"id": self.next_id}, "encoded_jit_config": "CONFIG"}
        return None


class FakeGuest:
    def __init__(self):
        self.calls = []

    def call(self, *args, stdin=None):
        self.calls.append(args)
        return ""


def job(labels=dispatch.LABELS, status="queued"):
    return {"status": status, "labels": list(labels)}


class TestServe(unittest.TestCase):
    def serve(self, runs, jobs, activity=(placed(),), runners=(), guest_units=None, dispatcher=None):
        github, guest = FakeGitHub(runs, jobs, list(activity), runners), FakeGuest()
        dispatcher = dispatcher or dispatch.Dispatcher(github=github, guest=guest)
        dispatcher.github, dispatcher.guest = github, guest
        dispatcher.inventory = {"dispatch": {"fci-rules-factory": REPO}, "persistent": {},
                                "jit": dict(guest_units or {})}
        started = dispatcher.serve("fci-rules-factory", REPO, 0)
        return started, github, guest

    def test_an_admitted_queued_job_is_written_into_the_guest_before_its_runner_starts(self):
        started, github, guest = self.serve([run(run_id=7)], {7: [job()]})
        self.assertEqual(1, started)
        self.assertEqual(("admit", "rules-factory", "7-1"), guest.calls[0])
        self.assertEqual("start", guest.calls[1][0])
        self.assertIn(("POST", f"/repos/{REPO}/actions/runners/generate-jitconfig"), github.posts)

    def test_a_fork_asking_for_factory_ci_is_cancelled_and_no_runner_starts_beside_it(self):
        """The forged `runs-on`: it is never served, and the owner's job waits until it is gone."""
        fork = run(event="pull_request", actor="outsider", head="outsider/rules-factory", run_id=8)
        started, github, guest = self.serve([run(run_id=7), fork], {7: [job()], 8: [job(["self-hosted"])]})
        self.assertEqual(0, started)
        self.assertIn(("POST", f"/repos/{REPO}/actions/runs/8/cancel"), github.posts)
        self.assertNotIn(("POST", f"/repos/{REPO}/actions/runners/generate-jitconfig"), github.posts)
        self.assertFalse([c for c in guest.calls if c[0] == "start"])

    def test_a_run_still_pending_blocks_runners_without_being_cancelled(self):
        started, github, guest = self.serve([run(run_id=7)], {7: [job()]}, activity=[])
        self.assertEqual(0, started)
        self.assertFalse(github.posts)

    def test_a_hosted_job_is_not_judged(self):
        fork = run(event="pull_request", actor="outsider", head="outsider/rules-factory", run_id=8)
        started, github, _ = self.serve([fork], {8: [job(["ubuntu-24.04"])]})
        self.assertEqual(0, started)
        self.assertFalse(github.posts, "a fork's hosted run is its own business")

    def test_a_repository_with_a_standing_runner_is_not_served(self):
        started, github, guest = self.serve([run(run_id=7)], {7: [job()]},
                                            runners=[{"id": 1, "name": "factory-ci-1", "status": "online", "busy": False}])
        self.assertEqual(0, started)
        self.assertFalse(guest.calls)

    def test_an_idle_runner_already_there_is_used_before_another_starts(self):
        idle = {"id": 50, "name": "factory-ci-1-jit-abcd", "status": "online", "busy": False}
        started, _, guest = self.serve([run(run_id=7)], {7: [job()]}, runners=[idle])
        self.assertEqual(0, started)
        self.assertFalse([c for c in guest.calls if c[0] == "start"])

    def test_a_runner_that_ran_its_one_job_and_left_is_not_counted_as_still_starting(self):
        """Seen 2026-10-10: a finished runner held a waiting job back until STARTING passed."""
        dispatcher = dispatch.Dispatcher(github=None, guest=None)
        first, _, _ = self.serve([run(run_id=7)], {7: [job()]}, dispatcher=dispatcher)
        self.assertEqual(1, first)
        runner_id = next(iter(dispatcher.spawned))
        listed = {"id": runner_id, "name": "factory-ci-1-jit-x", "status": "online", "busy": True}
        self.serve([run(run_id=7)], {7: [job(status="in_progress")]}, runners=[listed], dispatcher=dispatcher,
                   guest_units={runner_id: ("fci-rules-factory", "active")})
        second, _, _ = self.serve([run(run_id=8)], {8: [job()]}, dispatcher=dispatcher,
                                  guest_units={runner_id: ("fci-rules-factory", "inactive")})
        self.assertEqual(1, second, "the next admitted job gets a runner at once")

    def test_a_connecting_runner_whose_guest_unit_is_up_is_supply(self):
        connecting = {"id": 60, "name": "factory-ci-1-jit-y", "status": "offline", "busy": False}
        started, _, _ = self.serve([run(run_id=7)], {7: [job()]}, runners=[connecting],
                                   guest_units={60: ("fci-rules-factory", "active")})
        self.assertEqual(0, started)
        started, _, _ = self.serve([run(run_id=7)], {7: [job()]}, runners=[connecting],
                                   guest_units={60: ("fci-rules-factory", "inactive")})
        self.assertEqual(1, started, "an offline runner whose unit is down will never take it")

    def test_one_runner_per_admitted_queued_job_and_never_past_the_cap(self):
        runs = [run(run_id=i) for i in range(1, 7)]
        started, _, _ = self.serve(runs, {i: [job()] for i in range(1, 7)})
        self.assertEqual(dispatch.JIT_MAX, started)

    def test_a_running_job_needs_no_runner(self):
        started, _, _ = self.serve([run(run_id=7)], {7: [job(status="in_progress")]})
        self.assertEqual(0, started)


class TestTheGuestRefusesWhatWasNotAdmitted(unittest.TestCase):
    """The job-started hook is the second lock: read here as text, run for real on the VM."""

    def test_the_admission_check_comes_before_anything_the_job_could_influence(self):
        with open(os.path.join(os.path.dirname(PATH), "guest", "job-started.sh"), encoding="utf-8") as handle:
            hook = handle.read()
        check = hook.index('if [[ -e /etc/factory-ci/dispatch/$me ]]')
        self.assertLess(check, hook.index("find \"$GITHUB_WORKSPACE\""), "before the workspace is touched")
        self.assertLess(check, hook.index("slot-hold"), "before a slot is taken")
        self.assertIn("/run/factory-ci-trust/$me/$run-$attempt", hook[check:])
        self.assertIn('"$HOME"/jit/*/bin/Runner.Worker', hook[check:], "only a one-job runner serves a dispatch account")
        refusal = hook[check:hook.index("fi", hook.index("::error::", check))]
        self.assertIn('kill -KILL "$worker"', refusal,
                      "a failed hook does not stop the job: the runner still runs actions' pre and post steps")

    def test_admissions_live_where_no_runner_account_can_write(self):
        with open(os.path.join(os.path.dirname(PATH), "guest", "factory-ci.tmpfiles"), encoding="utf-8") as handle:
            self.assertIn("d /run/factory-ci-trust 0755 root root -", handle.read())



class TestThisRepositoryAsksForTheVmOnlyThroughTheContract(unittest.TestCase):
    """rules-factory is public: a literal self-hosted label in its workflows would be the direct path."""

    def test_every_runs_on_is_the_contract_line_or_the_pinned_hosted_release(self):
        sys.path.insert(0, os.path.join(os.path.dirname(HERE), "factory"))
        import repository
        workflows = os.path.join(os.path.dirname(os.path.dirname(HERE)), ".github", "workflows")
        seen = {}
        for name in sorted(os.listdir(workflows)):
            with open(os.path.join(workflows, name), encoding="utf-8") as handle:
                for line in handle.read().split("\n"):
                    if line.lstrip().startswith("runs-on:"):
                        self.assertIn(line, (repository.RUNS_ON_LINE, "    runs-on: ubuntu-24.04"), name)
                        seen.setdefault(name, []).append(line == repository.RUNS_ON_LINE)
        self.assertEqual([True, True], seen["validate.yml"], "validate and engine take the contract")
        self.assertEqual([True], seen["documentation.yml"])
        self.assertEqual([False, False], seen["publish-map.yml"], "publishing stays hosted: it holds the NuGet key")

if __name__ == "__main__":
    unittest.main()
