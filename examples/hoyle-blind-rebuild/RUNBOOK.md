# Runbook: the blind rebuild session

How to run rules-factory#3 criterion 1's rebuild so that its evidence holds. It follows Brandon's
decisions of 2026-09-15 ([README.md](README.md), "Decisions"). **An implementer may not read this
file**: it lives beside TARGET.json, which names every test.

Two roles:

- **The operator** has read this directory and may have seen the target: Brandon, or a coordinator
  acting for him. The operator prepares the workspace, answers questions, and judges.
- **The implementer** is a fresh agent context that has never seen hoyle-backgammon's code or tests,
  nor this directory, nor issue #3's thread. It sees only the brief.

## 1. The workspace

A directory outside every git repository, holding only the brief. For example `~/blind-rebuild`
(checked on 2026-09-15: `git -C /home/brandon rev-parse` fails, so `~` is not inside a repository):

```
~/blind-rebuild/                   outside every repository; the session never sees this level
  network-logs/                    the allowlist proxy's log; the session cannot reach it
  dotnet/                          optional: SDK 10.0.112 installed here, bound in read-only
  workspace/                       the ONLY host directory the session sees, at /workspace
    brief/                         the assembled brief, made read-only (chmod -R a-w)
    engine/                        the implementer's repository (git init here)
    questions/                     NNN-question.md from the implementer, NNN-answer.md from the operator
    home/                          HOME inside: NuGet packages, dotnet state, the agent's config and transcript
```

Prepare it, as the operator, outside the sandbox:

```bash
RB=~/blind-rebuild; mkdir -p "$RB"/{network-logs,workspace/{engine,questions,home}}
RF=~/rules-factory            # a rules-factory clone holding examples/hoyle-blind-rebuild and the factory tag
HB=/path/to/hoyle-backgammon  # a clone holding TARGET's engine commit
MAP=~/.nuget/packages/rulesfactory.maps.hoylebackgammon/6.0.0/rulesfactory.maps.hoylebackgammon.6.0.0.nupkg

python3 "$RF/examples/hoyle-blind-rebuild/check-target.py" "$HB" --factory "$RF" --nupkg "$MAP"
python3 "$RF/examples/hoyle-blind-rebuild/build-brief.py" api "$HB" --out "$RB/api-contract.raw.md"
python3 "$RF/examples/hoyle-blind-rebuild/build-brief.py" assemble "$HB" --factory "$RF" --nupkg "$MAP" \
    --api-contract "$RB/api-contract.raw.md" --out "$RB/workspace/brief"
python3 "$RF/examples/hoyle-blind-rebuild/build-brief.py" scan "$HB" --factory "$RF" --nupkg "$MAP" "$RB/workspace/brief"
chmod -R a-w "$RB/workspace/brief"
```

`scan` must print PASS, including that MANIFEST.json's sha256 equals TARGET `brief.manifestSha256`.
The brief holds the factory pre-staged at `inputs/factory/rules-factory/`, a clean checkout of
`factory/v0.7.0` with only the tools, so the session needs no github.com access (H8). The implementer
copies it out of the read-only brief before running it (`cp -a brief/inputs/factory/rules-factory
/workspace/factory`), because running the factory writes `__pycache__`.

**The SDK.** The factory's generated gate pins SDK 10.0.112 with roll-forward disabled. This machine
has 10.0.111 (snap). Either install 10.0.112 for the session, as the operator, before it starts
(`dotnet-install.sh --version 10.0.112 --install-dir ~/blind-rebuild/dotnet`, then
`DOTNET_ROOT=~/blind-rebuild/dotnet` when calling `run-isolated.sh`), or let the implementer use
`FACTORY_DOTNET_SDK_OVERRIDE=10.0.111` for local runs. The judgement runs in CI on 10.0.112 either way
(H11).

## 2. Isolation

### The allowlist

[sandbox/allowlist.txt](sandbox/allowlist.txt), HTTPS on port 443 only:

| Purpose | Hosts |
|---|---|
| NuGet | `api.nuget.org`, `globalcdn.nuget.org`, `www.nuget.org` |
| .NET SDK | `dot.net`, `builds.dotnet.microsoft.com`, `dotnetcli.azureedge.net`, `ci.dot.net` |
| Documentation | `learn.microsoft.com`, `xunit.net` |
| The session's model | `api.anthropic.com` |

No github.com host: the factory is pre-staged. Anything else, and every plain-HTTP request, is refused
and logged.

### How it is enforced here, without sudo

Tested on this machine (Ubuntu, kernel 6.17, uid 1000) on 2026-09-15:

| Mechanism | Available without sudo? | Finding |
|---|---|---|
| `sudo` | No | A password is required, so nothing needing root was used. |
| A dedicated user with `iptables -m owner` rules | No | Needs root for both `useradd` and `iptables`. |
| A container (docker, podman) | No | Neither is installed. |
| `unshare --user --net` | Yes | It gives a namespace with no network. With `--map-root-user` loopback can be brought up. The snap `dotnet` wrapper refuses to run inside, but the SDK binary itself does, from `/var/snap/dotnet/common/dotnet`. |
| bubblewrap (`/usr/bin/bwrap`) with `--unshare-all` | Yes | It works despite `kernel.apparmor_restrict_unprivileged_userns=1`. It hides the filesystem as well as the network. **This is what is used.** |

[sandbox/run-isolated.sh](sandbox/run-isolated.sh) `WORKSPACE -- COMMAND` runs the command under
bubblewrap:

- **Network:** new user, mount, PID and network namespaces. The network has loopback only.
- **Filesystem:** `/usr`, `/etc`, the lib directories, `/snap` and the SDK are read-only. `/tmp` is
  fresh. WORKSPACE is at `/workspace`, and `HOME` is `/workspace/home`. `/home`, `/root`, `~/.claude`,
  `~/.nuget` and every repository clone are invisible.
- **The proxy:** [sandbox/allowlist-proxy.py](sandbox/allowlist-proxy.py) runs outside, on a Unix
  socket. That socket is the only thing bound in from outside the workspace. A bridge inside forwards
  127.0.0.1:3128 to it, and `HTTPS_PROXY` points there.
- **Why it holds:** there is no route out, so a process that ignores the proxy reaches nothing.
- **The log:** every request goes to `LOGDIR/network.jsonl`, which defaults to
  `WORKSPACE/../network-logs`, outside the session's view.

[sandbox/probe.sh](sandbox/probe.sh), run inside on 2026-09-15:

```
allowed:  https://api.nuget.org/v3/index.json              200
allowed:  https://learn.microsoft.com/dotnet/              302
refused:  https://github.com/ (via proxy)                  000 (failed)
refused:  https://example.com/ (via proxy)                 000 (failed)
refused:  http://example.com/ (plain http)                 403
bypass:   https://api.nuget.org/ with --noproxy '*'        000 (failed)
bypass:   direct IP 140.82.112.3:443                       000 (failed)
8.0.130 [/opt/dotnet/sdk]
10.0.111 [/opt/dotnet/sdk]
filesystem: /home                                          not visible
filesystem: /root                                          not visible
filesystem: /var/snap                                      not visible
filesystem: /tmp/claude-1000                               not visible
filesystem: / holds                                        bin dev etc lib lib32 lib64 opt proc run sbin snap tmp usr workspace
```

A real `dotnet restore` of a factory-produced HoyleBackgammon engine ran inside the sandbox through the
proxy and succeeded. NuGet's certificate revocation checks go out over plain HTTP (`ocsp.digicert.com`,
`crl3.digicert.com`); they were refused and logged, and restore still succeeded. The log recorded each
refused github.com attempt, and `search-transcript.py` failed on them, as it should.

### What is not enforced, and what Brandon would need to do

The sandbox confines whatever runs inside it. **The implementer is only confined if the agent runs
inside too.** An agent running outside, which only sends some commands through `run-isolated.sh`,
still has its own file-reading and web tools on the host. For such a session, blindness is attested
and searched, not enforced.

This machine has no Claude Code CLI on `PATH`; this session runs in the desktop app, which cannot be
started inside bubblewrap. So an agent running inside was **not tested**. To enforce it, Brandon would:

1. Install the Claude Code CLI to a directory outside `/home/brandon/rules-factory` and outside the
   workspace, for example `~/blind-rebuild/tools`.
2. Start it inside the sandbox with a fresh HOME:
   `EXTRA_RO_BINDS=~/blind-rebuild/tools DOTNET_ROOT=... examples/hoyle-blind-rebuild/sandbox/run-isolated.sh ~/blind-rebuild/workspace -- ~/blind-rebuild/tools/claude`
3. Log in inside it. The fresh HOME has no credentials, and entering them is his action. If the login
   flow needs hosts beyond `api.anthropic.com`, the refused hosts appear in `network.jsonl`. Add
   exactly those to `allowlist.txt` for the login only, and record that in the evidence.
4. Give it only `brief/README.md` as its first instruction, and keep `home/.claude/projects/`, where
   the transcript is written.

Alternatives that need root, if Brandon prefers them:

- a dedicated user with iptables owner rules: `sudo useradd -m blindrebuild`, then
  `sudo iptables -A OUTPUT -m owner --uid-owner blindrebuild ! -o lo -j REJECT`, with the proxy on
  loopback;
- a rootless container runtime: `sudo apt install podman`, and the same allowlist as an HTTP proxy.

Neither is needed for the mechanism above.

## 3. Questions

Written questions are allowed (H3).

1. The implementer writes `/workspace/questions/NNN-question.md` (001, 002, ...), one question per
   file, and carries on, or waits.
2. The operator writes the answer outside the workspace, in terms of behaviour. It holds no test name,
   no test data and no code from the target. It must pass the brief's leak check before it is handed
   over:
   `python3 "$RF/examples/hoyle-blind-rebuild/build-brief.py" check-text "$HB" --factory "$RF" --nupkg "$MAP" NNN-answer.md`
3. The operator copies `NNN-answer.md` into `workspace/questions/`. An answer that cannot be given
   without leaking is written as a refusal ("not answerable from the brief"), which also counts.
4. Every question and answer is published with the result. More than 10 answers labels the result
   "assisted", otherwise "blind"; either way it is "with a written interface" (H1, H2), because the
   brief carries `api-contract.md` and `conventions.md`. `check-rebuild.py --questions` prints the
   label.

## 4. After the session: the transcript search

Run as the operator, before anything else is done with the result:

```bash
python3 "$RF/examples/hoyle-blind-rebuild/search-transcript.py" \
    --network-log ~/blind-rebuild/network-logs/network.jsonl \
    ~/blind-rebuild/workspace/home/.claude/projects/*/*.jsonl \
    ~/blind-rebuild/workspace/questions/*.md
```

**FAIL** on any of:

- a target test method name the brief does not disclose;
- a tool call naming github.com, hoyle-backgammon, `hoyle-blind-rebuild`, or rules-factory's
  `examples/`, `tools/tests/`, issues or pulls;
- a refused request to a github host;
- an allowed request to a host that is not on the allowlist.

**REVIEW** lines (a target test class name, other refused requests) are read and explained in the
evidence. If the agent ran outside the sandbox, say so in the evidence: the search then covers what
the transcript shows, and nothing else.

## 5. Judgement in CI

Brandon's decision is to run it in CI on SDK 10.0.112 (H11).

1. The operator pushes the implementer's `engine/` repository, unchanged, to a public GitHub
   repository, and waits for its own `validate` workflow to go green. That is P5's CI half.
2. The operator dispatches rules-factory's
   [judge-rebuild](../../.github/workflows/judge-rebuild.yml) workflow. `workflow_dispatch` runs only
   once the workflow is on `main`:

   ```bash
   gh workflow run judge-rebuild.yml --repo brandonifco/rules-factory \
       -f rebuild_repository=OWNER/NAME -f rebuild_commit=FULL_SHA
   gh run watch --repo brandonifco/rules-factory
   ```

   It clones the target and the rebuild, and installs the SDK the target's `global.json` pins. It runs
   `check-rebuild.py` (P1 to P4, with the pass count printed either way), then `factory provenance` on
   the rebuild with the factory checked out at the tag (P5). Both go to the job summary.
3. Locally, the same check without CI is
   `check-rebuild.py REBUILD ENGINE --commit SHA --questions ~/blind-rebuild/workspace/questions`.
   It is NOT VERIFIED on another SDK.
4. The evidence pull request adds `EVIDENCE.md` to this directory ([EQUIVALENCE.md](EQUIVALENCE.md),
   A3). It holds:
   - the judge-rebuild run link and summary;
   - the pass count;
   - the label;
   - every question and answer;
   - the search-transcript output with its REVIEW lines explained;
   - the network log's refused requests;
   - whether the agent ran inside the sandbox;
   - the P4 reviewer's statement.
