"""The licensed-copy exception (#105, decision 0022): who may use a `local-copy` corpus, and how that is shown.

A `local-copy` corpus (0013) is licensed: its bytes are not in the repository, and a map quoting it
must not be redistributed. The factory refuses it at every step. One named operator, who holds a
licensed copy, may use one on their own machine, and only for what stays on that machine: pack a
map into a local `.nupkg`, and `produce`, `verify` and `provenance` an engine from it. Nothing that
distributes is covered: publishing is refused whatever this module says.

The exception is honoured only when all of these hold, and a failure of any one is a refusal:

  * the command was given `--licensed-copy-exception` (FLAG). Without it, nothing here runs and
    every existing refusal fires with its existing message;
  * the run is not in CI: `GITHUB_ACTIONS` is not set, and `CI` is unset or false. A CI runner is
    where publishing happens, and nobody's licensed copy lives there;
  * the identity `gh` is authenticated as -- `gh api user --jq .login`, through `$FACTORY_GH` when set,
    as backlog.py runs it, with a timeout -- is in ALLOWLIST. `gh` missing, unauthenticated, hung
    or erroring is a refusal, never a fallback. `git config` is never read: anyone can set it.

ALLOWLIST is `licensed-copy-operators.json` beside this file, a committed list of GitHub logins that
changes only by pull request. It holds `brandonifco`.

**A guardrail against accidental use and accidental distribution, not a security boundary.** Anyone
who can edit this checkout can edit the list, this module or `$FACTORY_GH`. What it prevents is a
licensed corpus being used, or a map of one being packed, by someone who did not mean to and would
not notice: a contributor, a CI job, the operator on the wrong account.

Standard library only. Not vendored into engines (gate.py): intake.py and provenance.py, which are,
never import it; they are told the operator's login by the caller.
"""
import json
import os
import re
import subprocess

FLAG = "--licensed-copy-exception"
HERE = os.path.dirname(os.path.abspath(__file__))
ALLOWLIST = os.path.join(HERE, "licensed-copy-operators.json")
# Seconds `gh api user` may take: an auth prompt or a stalled network is a refusal, not a wait.
GH_TIMEOUT = 60
LOGIN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")
FALSE = ("", "0", "false", "no")


class Refused(Exception):
    """The exception was asked for and is not honoured."""


def attestation(operator):
    """What every output line that would otherwise say verified says under the exception."""
    return f"verified locally under the licensed-copy exception by {operator}"


def in_ci(env=None):
    env = os.environ if env is None else env
    return (env.get("GITHUB_ACTIONS", "").strip().lower() not in FALSE
            or env.get("CI", "").strip().lower() not in FALSE)


def operators(path=None):
    """The allowlisted logins, compared case-insensitively as GitHub compares them."""
    path = path or ALLOWLIST
    try:
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
    except (OSError, ValueError) as error:
        raise Refused(f"cannot read the licensed-copy allowlist {path}: {error}")
    listed = document.get("operators") if isinstance(document, dict) else None
    if not isinstance(listed, list) or not listed or not all(isinstance(o, str) and LOGIN.match(o) for o in listed):
        raise Refused(f"{path}: `operators` is not a non-empty list of GitHub logins")
    return listed


def authenticated_login(gh=None, env=None):
    """The login `gh` is authenticated as. Any failure to establish it is a refusal."""
    env = os.environ if env is None else env
    gh = gh or env.get("FACTORY_GH") or "gh"
    try:
        done = subprocess.run([gh, "api", "user", "--jq", ".login"], capture_output=True, text=True,
                              timeout=GH_TIMEOUT, stdin=subprocess.DEVNULL, env=dict(env))
    except OSError as error:
        raise Refused(f"cannot run {gh} to establish who is running this ({error}); the exception needs the "
                      f"authenticated GitHub identity, and nothing else stands in for it")
    except subprocess.TimeoutExpired:
        raise Refused(f"`{gh} api user` did not finish in {GH_TIMEOUT} seconds, so no identity was established")
    if done.returncode != 0:
        raise Refused(f"`{gh} api user` failed ({done.stderr.strip() or done.stdout.strip() or done.returncode}); "
                      f"run `gh auth login` as an allowlisted operator")
    login = done.stdout.strip()
    if not LOGIN.match(login):
        raise Refused(f"`{gh} api user --jq .login` printed {login!r}, which is not a GitHub login")
    return login


def authorise(gh=None, env=None, allowlist=None):
    """The allowlisted operator's login, or Refused. Called only when FLAG was given."""
    env = os.environ if env is None else env
    allowlist = allowlist or ALLOWLIST
    if in_ci(env):
        raise Refused(f"{FLAG} is refused in CI (CI or GITHUB_ACTIONS is set): the exception covers an "
                      f"operator's own machine, never a runner (0022)")
    listed = operators(allowlist)
    login = authenticated_login(gh, env)
    if login.lower() not in {o.lower() for o in listed}:
        raise Refused(f"{FLAG}: gh is authenticated as {login}, who is not in {os.path.basename(allowlist)} "
                      f"({', '.join(listed)}); the list changes only by pull request (0022)")
    return next(o for o in listed if o.lower() == login.lower())
