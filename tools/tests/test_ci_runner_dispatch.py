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
    def __init__(self, runs, jobs, activity, runners=(), fail_cancel=0):
        self.runs, self.jobs, self.activity, self.runners = runs, jobs, activity, list(runners)
        self.posts, self.next_id, self.fail_cancel, self.link = [], 100, fail_cancel, ""

    def page(self, items, path):
        page = int(path.rsplit("page=", 1)[1]) if "page=" in path else 1
        return items[(page - 1) * 100:page * 100]

    def every(self, path, key, cache=True, pages=10):
        return dispatch.GitHub.every(self, path, key, cache, pages)

    def get(self, path, cache=False):
        if "/actions/runs?status=" in path:
            status = path.split("status=")[1].split("&")[0]
            return {"workflow_runs": self.page([r for r in self.runs if r.get("status", "queued") == status], path)}
        if "/jobs" in path:
            run_id = int(path.split("/actions/runs/")[1].split("/")[0])
            return {"jobs": self.page(self.jobs.get(run_id, []), path)}
        if "/activity" in path:
            return self.activity
        if "/actions/runners?" in path:
            return {"runners": self.page(self.runners, path)}
        raise AssertionError(path)

    def next_link(self):
        return None

    def call(self, method, path, body=None, cache=False):
        if path.endswith("/cancel") and self.fail_cancel:
            self.fail_cancel -= 1
            self.posts.append((method, path))
            raise dispatch.urllib.error.HTTPError(path, 503, "unavailable", {}, None)
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


FORK = dict(event="pull_request", actor="outsider", head="outsider/rules-factory")


class TestServe(unittest.TestCase):
    def serve(self, runs, jobs, activity=(placed(),), runners=(), guest_units=None, dispatcher=None, fail_cancel=0):
        github, guest = FakeGitHub(runs, jobs, list(activity), runners, fail_cancel), FakeGuest()
        dispatcher = dispatcher or dispatch.Dispatcher(github=github, guest=guest)
        dispatcher.github, dispatcher.guest = github, guest
        dispatcher.inventory = {"dispatch": {"rules-factory": REPO}, "persistent": {}, "jit": dict(guest_units or {})}
        started = dispatcher.serve("rules-factory", REPO, 0)
        return started, github, guest

    def starts(self, guest):
        return [c for c in guest.calls if c[0] == "start"]

    def test_an_admitted_queued_job_is_written_into_the_guest_before_its_runner_starts(self):
        started, github, guest = self.serve([run(run_id=7)], {7: [job()]})
        self.assertEqual(1, started)
        self.assertEqual(("admit", "rules-factory", "7-1"), guest.calls[0])
        self.assertEqual(("start", "rules-factory", "a", "101"), guest.calls[-1])
        self.assertIn(("POST", f"/repos/{REPO}/actions/runners/generate-jitconfig"), github.posts)

    def test_a_fork_asking_for_factory_ci_is_cancelled_and_no_runner_starts_beside_it(self):
        """The forged `runs-on`: it is never served, and the owner's job waits until it is gone."""
        started, github, guest = self.serve([run(run_id=7), run(run_id=8, **FORK)], {7: [job()], 8: [job(["self-hosted"])]})
        self.assertEqual(0, started)
        self.assertIn(("POST", f"/repos/{REPO}/actions/runs/8/cancel"), github.posts)
        self.assertNotIn(("POST", f"/repos/{REPO}/actions/runners/generate-jitconfig"), github.posts)
        self.assertFalse(self.starts(guest))

    def test_a_refusal_retires_every_runner_still_waiting(self):
        """Codex 2026-10-10 (P1): a listener left idle beside a refused job could be handed it."""
        idle = {"id": 50, "name": "factory-ci-1-jit-abcd", "status": "online", "busy": False}
        working = {"id": 51, "name": "factory-ci-1-jit-beef", "status": "online", "busy": True}
        _, github, guest = self.serve([run(run_id=7), run(run_id=8, **FORK)], {7: [job()], 8: [job()]}, runners=[idle, working])
        self.assertIn(("DELETE", f"/repos/{REPO}/actions/runners/50"), github.posts)
        self.assertNotIn(("DELETE", f"/repos/{REPO}/actions/runners/51"), github.posts, "a running job is left alone")
        self.assertIn(("stop", "50"), guest.calls)

    def test_a_fork_job_past_the_first_page_is_still_seen(self):
        """Codex 2026-10-10 (P1): a fork hid its self-hosted job behind a hundred hosted ones."""
        jobs = [job(["ubuntu-24.04"])] * 100 + [job(["self-hosted"])]
        started, github, _ = self.serve([run(run_id=7), run(run_id=8, **FORK)], {7: [job()], 8: jobs})
        self.assertEqual(0, started)
        self.assertIn(("POST", f"/repos/{REPO}/actions/runs/8/cancel"), github.posts)

    def test_a_list_too_long_to_read_whole_starts_nothing(self):
        runs = [run(run_id=i, **FORK) for i in range(1, 1102)]
        with self.assertRaises(dispatch.Incomplete):
            self.serve(runs, {})

    def test_a_failed_cancel_is_asked_again_and_then_forced(self):
        """Codex 2026-10-10 (P2): one 503 used to end every later attempt to cancel."""
        dispatcher = dispatch.Dispatcher(github=None, guest=None)
        fork = run(run_id=8, **FORK)
        for _ in range(4):
            _, github, _ = self.serve([fork], {8: [job()]}, dispatcher=dispatcher, fail_cancel=1)
        self.assertIn(("POST", f"/repos/{REPO}/actions/runs/8/force-cancel"), github.posts)

    def test_a_re_run_of_a_refused_run_is_cancelled_again(self):
        dispatcher = dispatch.Dispatcher(github=None, guest=None)
        self.serve([run(run_id=8, **FORK)], {8: [job()]}, dispatcher=dispatcher)
        _, github, _ = self.serve([run(run_id=8, attempt=2, triggering=OWNER, **{k: v for k, v in FORK.items()})],
                                  {8: [job()]}, dispatcher=dispatcher)
        self.assertIn(("POST", f"/repos/{REPO}/actions/runs/8/cancel"), github.posts)

    def test_a_run_still_pending_blocks_runners_without_being_cancelled(self):
        started, github, guest = self.serve([run(run_id=7)], {7: [job()]}, activity=[])
        self.assertEqual(0, started)
        self.assertFalse([p for p in github.posts if p[1].endswith("cancel")])

    def test_a_hosted_job_is_not_judged(self):
        started, github, _ = self.serve([run(run_id=8, **FORK)], {8: [job(["ubuntu-24.04"])]})
        self.assertEqual(0, started)
        self.assertFalse(github.posts, "a fork's hosted run is its own business")

    def test_a_repository_with_a_standing_runner_is_not_served(self):
        started, github, guest = self.serve([run(run_id=7)], {7: [job()]},
                                            runners=[{"id": 1, "name": "factory-ci-1", "status": "online", "busy": False}])
        self.assertEqual(0, started)
        self.assertFalse(self.starts(guest))

    def test_an_idle_runner_already_there_is_used_and_the_run_admitted_for_it(self):
        """Codex 2026-10-10 (P2): reusing a waiting runner wrote no admission, so the hook killed the job."""
        idle = {"id": 50, "name": "factory-ci-1-jit-abcd", "status": "online", "busy": False}
        started, _, guest = self.serve([run(run_id=7)], {7: [job()]}, runners=[idle],
                                       guest_units={50: ("fci-rules-factory", "active")})
        self.assertEqual(0, started)
        self.assertIn(("admit", "rules-factory", "7-1"), guest.calls)

    def test_an_account_never_has_two_runners(self):
        """Codex 2026-10-10 (P0): a job could rewrite a sibling listener of its own UID."""
        started, _, guest = self.serve([run(run_id=i) for i in (1, 2, 3)], {i: [job()] for i in (1, 2, 3)})
        self.assertEqual(2, started, "one per lane")
        self.assertEqual({"a", "b"}, {c[2] for c in self.starts(guest)})
        busy = {60: ("fci-rules-factory", "active")}
        working = {"id": 60, "name": "factory-ci-1-jit-x", "status": "online", "busy": True}
        started, _, guest = self.serve([run(run_id=i) for i in (1, 2, 3)], {i: [job()] for i in (1, 2, 3)},
                                       runners=[working], guest_units=busy)
        self.assertEqual([("start", "rules-factory", "b", "101")], self.starts(guest))

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

    def test_never_past_the_cap(self):
        github, guest = FakeGitHub([run(run_id=1)], {1: [job()]}, [placed()]), FakeGuest()
        dispatcher = dispatch.Dispatcher(github=github, guest=guest)
        dispatcher.inventory = {"dispatch": {}, "persistent": {}, "jit": {}}
        self.assertEqual(0, dispatcher.serve("rules-factory", REPO, dispatch.JIT_MAX))

    def test_a_running_job_needs_no_runner(self):
        started, _, _ = self.serve([run(run_id=7)], {7: [job(status="in_progress")]})
        self.assertEqual(0, started)


class TestTheGuestIsSpokenToSafely(unittest.TestCase):
    """Codex 2026-10-10 (P0): an account-written .runner became a root command on the host's way in."""

    def test_an_injected_line_is_one_value_and_never_a_second_entry(self):
        forged = ('{"kind":"persistent","account":"fci-x","url":"x\\ndispatch fci-$(touch /tmp/p) a/b"}\n'
                  'dispatch fci-$(touch /tmp/p) brandonifco/rules-factory\n'
                  '{"kind":"dispatch","name":"$(id)","repo":"a/b"}\n'
                  '{"kind":"dispatch","name":"rules-factory","repo":"brandonifco/rules-factory"}\n'
                  '{"kind":"jit","id":"7","account":"fci-rules-factory","state":"active"}\n')
        found = dispatch.parse_inventory(forged)
        self.assertEqual({"rules-factory": "brandonifco/rules-factory"}, found["dispatch"])
        self.assertEqual({7: ("fci-rules-factory", "active")}, found["jit"])
        self.assertEqual(["fci-x"], list(found["persistent"]), "the URL is data, never acted on")

    def test_an_argument_with_shell_in_it_is_never_sent(self):
        for arg in ("$(id)", "a b", "a;b", "`x`", "a\nb", "'"):
            with self.assertRaises(ValueError, msg=arg):
                dispatch.Guest.call("admit", arg)


class TestTheGuestRefusesWhatWasNotAdmitted(unittest.TestCase):
    """The job-started hook is the second lock: read here as text, run for real on the VM."""

    def read(self, name):
        with open(os.path.join(os.path.dirname(PATH), "guest", name), encoding="utf-8") as handle:
            return handle.read()

    def test_the_admission_check_comes_before_anything_the_job_could_influence_and_fails_closed(self):
        hook = self.read("job-started.sh")
        check = hook.index('if [[ $exe == /srv/factory-ci-jit/*')
        self.assertLess(check, hook.index("find \"$GITHUB_WORKSPACE\""), "before the workspace is touched")
        self.assertLess(check, hook.index("slot-hold"), "before a slot is taken")
        self.assertIn("! -r /etc/factory-ci/dispatch-accounts", hook[check:check + 200],
                      "an unreadable policy refuses, never skips (Codex 2026-10-10, P0)")
        for needed in ("/run/factory-ci-trust/runners/", "after its lease", "/run/factory-ci-trust/$name/$run-$attempt"):
            self.assertIn(needed, hook[check:])
        refusal = hook[hook.index('if [[ -n $why ]]', check):]
        self.assertIn('kill -KILL "$worker"', refusal[:refusal.index("fi\n")],
                      "a failed hook does not stop the job: the runner still runs actions' pre and post steps")

    def test_admissions_live_where_no_runner_account_can_write(self):
        tmpfiles = self.read("factory-ci.tmpfiles")
        self.assertIn("d /run/factory-ci-trust 0755 root root -", tmpfiles)
        self.assertIn("d /run/factory-ci-trust/runners 0755 root root -", tmpfiles)

    def test_root_builds_a_runner_where_no_account_can_write_and_hands_it_over_whole(self):
        """Codex 2026-10-10 (P0): root's `install -d` followed a link a job left in its home."""
        start = self.read("dispatch-guest.sh")
        start = start[start.index("cmd_start() {"):start.index("cmd_stop()")]
        self.assertIn('dir="$jits/$id"', start)
        self.assertLess(start.index('mkdir -m 0700 "$dir"'), start.index('chown -R "$user:$user" "$dir"'))
        self.assertLess(start.index('.jitconfig"; chmod 0600'), start.index('chown -R'), "filled before it is handed over")
        self.assertNotIn("runuser", start, "nothing is done as the account before the handover")
        self.assertIn('busy "$user" && die', start, "one runner per account (Codex 2026-10-10, P0)")

    def test_register_writes_below_a_home_as_its_account(self):
        register = self.read("register.sh")
        body = register[register.index('systemctl stop "factory-ci-runner@$user"'):]
        for line in body.splitlines():
            if any(word in line for word in ("install ", "rm -f", "tar ")):
                self.assertIn("runuser -u \"$user\"", line, line)


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
