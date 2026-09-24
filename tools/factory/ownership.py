"""Who owns each file `produce` writes (#72, decision 0018). One table, three classes.

Before this module the factory had generated files, a one-shot template scaffold and nothing
saying which was which: global.json, NuGet.config and Directory.Build.props were written once
and then belonged to the engine, so a factory change to SDK policy, package sources, analyzers
or target frameworks never reached an engine that had already been produced. `TABLE` below is
now the only place a file's class is decided; generate.py, provenance.py and the tests read it,
and the ADR's table is checked against it.

  * **generated** -- rewritten on every `produce` from the factory's inputs. A hand edit is
    overwritten, and provenance.json hashes each one in `generated`, so an edit made after the
    last `produce` is a named mismatch.
  * **managed** -- factory policy the engine should keep receiving. Each managed file has a
    recipe version, and `RECIPE_SHA256` lists the SHA-256 of the bytes every version of its
    recipe ever wrote. On each `produce` a managed file that is absent, or whose bytes are one
    of those versions, is (re)written from the current recipe: that is the migration. A managed
    file whose bytes are none of them has been edited by hand, and `produce` refuses, naming
    it, before anything is written, rather than overwrite a deliberate change or silently keep
    a stale policy. Two flags settle it: `--adopt PATH` makes the file engine-owned from then
    on (provenance.json records the adoption, so later runs remember it), and `--reset PATH`
    overwrites it with the current recipe and makes it managed again (also how an adopted file
    comes back). provenance.json hashes each managed file once, in `managed`, with its recipe
    version.
  * **engine-owned** -- written once, when absent, and never touched again: the engine's own
    choices, which no factory change should undo. provenance.json lists them in `engineOwned`
    and hashes them, as it hashes every build input the engine owns, in `buildInputs`.

Detection compares against the recipe history in code rather than against the hash the last
`produce` recorded in provenance.json. The history does not trust a file in the engine (an edited
provenance.json cannot make a hand edit look like the factory's), it works for an engine produced
before this module existed (its files are version 1), and it makes a recipe version mean fixed
bytes: tools/tests/factory/test_factory_ownership.py fails when a recipe changes without a new version and
its hash. The cost is that a managed recipe may not depend on the engine's name or the map, and
none does.

Anything `produce` writes must match exactly one row; provenance.build refuses a written path
that matches none, so a new output cannot ship unclassified. The lock files are the one output
not written by Python: verify's first restore (verify.py) writes them in the staging copy when
none exist, and produce commits them. They are engine-owned: the engine relocks
(`scripts/validate.sh lock`) and commits them itself, and a later produce leaves them alone, with
one exception (#94, decision 0018's amendment): a produce that changes the generated pins in
RulesFactory.Packages.g.props (a map version bump) re-locks every existing lock file in its
staging copy before the gate, because lock files resolved against the old pins cannot pass the
gate's locked restore. The rewrite is the consequence of the factory's input moving, is recorded
in provenance.json, and is committed only if the gate passes. Files the engine adds itself (its
hand-written code, lock files) match no row and are not the factory's to classify.

`RETIRED` is the other direction: a pattern `produce` **once wrote and now removes**. It is not a
fourth class -- nothing writes a retired path and nothing hashes one -- but a file the factory
stops writing does not become the engine's by default, so every run deletes what the patterns match
(`remove_retired`) and that deletion is still recognisably the factory's work.

Standard library only; vendored into every engine as scripts/factory/ownership.py because
generate.py imports it and the engine's gate imports generate.py.
"""
import collections
import fnmatch
import hashlib
import json
import os
import re

import overlay

GENERATED = "generated"
MANAGED = "managed"
ENGINE_OWNED = "engine-owned"
CLASSES = (GENERATED, MANAGED, ENGINE_OWNED)
PROVENANCE = "provenance.json"

Row = collections.namedtuple("Row", "pattern cls recipe reason")

# `{name}` is the engine name; `*` matches within one path segment only.
TABLE = (
    Row("provenance.json", GENERATED, None,
        "the record of this run; written last, from the run itself"),
    Row("RulesFactory.Packages.g.props", GENERATED, None,
        "the kernel and map pins and the map reference: facts about the inputs (#66)"),
    Row("src/{name}/Generated/*.g.cs", GENERATED, None,
        "the map, registry, typed contracts and embedded provenance, from merge(package, overlay)"),
    Row("tests/{name}.Tests/Generated/*.g.cs", GENERATED, None,
        "the correspondence and provenance tests, from the same merge"),
    Row("corpus/*", GENERATED, None,
        "the corpus copy intake proved against the map's baseline"),
    Row("scripts/validate.sh", GENERATED, None, "the gate recipe (M3): the factory's definition of acceptable"),
    Row("scripts/map-overlay.py", GENERATED, None, "the gate recipe: 0015's merge"),
    Row("scripts/engine-gate.py", GENERATED, None, "the gate recipe: its non-dotnet checks"),
    Row("scripts/factory/*.py", GENERATED, None, "the factory's generator, vendored so the gate can regenerate"),
    Row(".github/workflows/validate.yml", GENERATED, None, "the gate recipe: CI runs validate.sh full"),
    Row("AGENTS.md", MANAGED, 19,
        "the governing contract every agent works this engine under (decision 0029); section 4 carries "
        "the sweep, the documentation section, and delete-only-what-you-created (#236); a packet that "
        "names an entry is made with the map the reviewed commit declares (#372); section 11 is what the "
        "machine owes the work -- the pinned SDK, a restore, a `gh` the packets can read (#195); section 9 "
        "names the two emitted things that do name a vendor, as the defaults they are (#174)"),
    Row("CLAUDE.md", MANAGED, 1,
        "a pointer to AGENTS.md and the Claude adapters; it states no rule of its own (0029)"),
    Row("docs/agent-team.md", MANAGED, 5, "the four roles, and what each may not do (0029)"),
    Row(".claude/agents/engine-dev.md", MANAGED, 9, "the implementer's charter (0029)"),
    Row(".claude/agents/repo-steward.md", MANAGED, 1, "the structural reviewer's charter, read-only (0029)"),
    Row(".claude/agents/rules-conformance.md", MANAGED, 4, "the semantic reviewer's charter, read-only (0029)"),
    Row(".claude/hooks/primary-checkout-guard.py", MANAGED, 1,
        "the PreToolUse guard that keeps implementation work out of the primary checkout (0029)"),
    Row(".claude/settings.json", MANAGED, 1, "which tools the guard runs before (0029)"),
    Row("tools/dispatch-agent.sh", MANAGED, 4,
        "one issue, one worktree, one branch; it refuses what is not ready to work, and --sweep "
        "removes what merged work left behind, before every dispatch (0029, #236)"),
    Row("tools/new-issue.sh", MANAGED, 2,
        "an issue with the shape the rails expect, a factory update's included (0029, #193)"),
    Row("tools/entry-packet.py", MANAGED, 6,
        "the bounded assignment for one entry, assembled from merge(package, overlay) (0029)"),
    Row("tools/mutate.py", MANAGED, 1,
        "a recorded mutation, run: the edit, the named test, and the source put back, so the evidence "
        "AGENTS.md asks for is re-runnable by the reviewer rather than a sentence (#454)"),
    Row("tools/re-produce.sh", MANAGED, 6,
        "an overlay edit is finished by a re-produce, from the factory commit the record names (#192); "
        "a record a merge left conflicted is named as one, and --resolve-record settles it (#252)"),
    Row("tools/review-packet.py", MANAGED, 7,
        "everything a reviewer needs about one pull request, in the order it is read (0029); the map is "
        "read once and the entry packets are built from those bytes, and a refused packet writes nothing "
        "(#371, #372)"),
    Row("tools/pr-policy.py", MANAGED, 7,
        "the pull request contract, checked mechanically; a produce update's claim is checked, not taken "
        "(#193); every document the engine owns is accounted for (#236)"),
    Row("tools/record-verdict.py", MANAGED, 3,
        "a review verdict as a commit status on the exact commit reviewed, from entry evidence bound to "
        "that commit (0029, #372)"),
    Row("tools/conformance-gate.py", MANAGED, 3,
        "whether the verdicts this change needs are recorded at the commit being merged; a truncated "
        "file list is undecidable (0029, #193)"),
    Row("tools/requeue-gate.py", MANAGED, 2,
        "asks the gate to report again when something outside the pull request changed what it "
        "would answer: a verdict recorded at its head (#191), or the risk label on the issue it "
        "closes (#230)"),
    Row(".github/pull_request_template.md", MANAGED, 4,
        "the pull request shape pr-policy.py checks, documentation section included (0029, #236); "
        "\"Unrelated changes\" says what belongs in it and what is part of the change (#196)"),
    Row(".github/workflows/pr-policy.yml", MANAGED, 1, "the required check that runs pr-policy.py (0029)"),
    Row(".github/workflows/conformance-gate.yml", MANAGED, 2,
        "the required check that runs conformance-gate.py (0029)"),
    Row(".github/workflows/verdict-requeue.yml", MANAGED, 2,
        "runs requeue-gate.py on the status and issues events; deliberately not a required check "
        "(#191, #230)"),
    Row("tools/agent-doctor.py", MANAGED, 6,
        "whether the rails are active or only present, locally and on GitHub, and what merged work "
        "left behind (0029, #236); the machine's own prerequisites first, because a rail in place on a "
        "machine that cannot run the gate stops nothing (#195)"),
    Row(".editorconfig", MANAGED, 1,
        "the kernel determinism analyzers' severities: a build error in src, off in tests (0029)"),
    Row("global.json", MANAGED, 1,
        "the kernel's SDK pin and roll-forward policy; an engine that must move it adopts it"),
    Row("NuGet.config", MANAGED, 2,
        "package sources and source mapping: supply-chain policy; an extra feed is an adoption"),
    Row("Directory.Build.props", MANAGED, 2,
        "target frameworks, analyzers, warnings-as-errors, determinism and lock-file policy"),
    Row("Directory.Packages.props", ENGINE_OWNED, None,
        "central package management and the test packages an engine bumps; imports the generated pins"),
    Row("{name}.slnx", ENGINE_OWNED, None, "the engine adds projects to its solution"),
    Row("src/{name}/{name}.csproj", ENGINE_OWNED, None, "the engine adds references and files"),
    Row("tests/{name}.Tests/{name}.Tests.csproj", ENGINE_OWNED, None, "the engine adds test references"),
    Row(f"{overlay.DIRECTORY}/*{overlay.SUFFIX}", ENGINE_OWNED, None,
        "the engine's three fields for one entry, one file per entry (0015, #247)"),
    Row(".github/agent-policy.json", ENGINE_OWNED, None,
        "the engine's own rails configuration: labels, review contexts and chain, worktree "
        "variables. Written once so a factory change can never undo a consumer's choice (0029)"),
    Row("src/{name}/packages.lock.json", ENGINE_OWNED, None,
        "written by verify's first restore when absent, then reviewed, committed and relocked by the engine; "
        "re-locked by a produce that changes the generated pins (#94)"),
    Row("tests/{name}.Tests/packages.lock.json", ENGINE_OWNED, None, "the same, for the test project"),
)

Retired = collections.namedtuple("Retired", "pattern reason witness")

#: The witnesses a retirement may be authorised by, by name (`Retired.witness`). A witness is
#: `(root, relative, bytes) -> why it may not be deleted, or None`, and it is what the deletion
#: rests on when the record cannot carry it.
#:
#: There is exactly one, and adding a second is a decision, not a convenience: every entry here is
#: another sentence that ends "...and so these bytes may be deleted". `superseded_by_split` is the
#: overlay's (#247) -- see `WROTE_IT` below for why the record could not carry that one.
WITNESSES = {"overlay-split": overlay.superseded_by_split}

#: `Retired.witness` for the ordinary retirement: no witness, so the record decides.
WROTE_IT = None

#: Patterns `produce` **once wrote and now removes**. A file the factory stopped writing does not
#: become the engine's by default: an engine produced before the retirement still has it committed,
#: hashed by a record that no longer mentions it, and nobody would think to delete it. So each
#: `produce` removes what these match (`remove_retired`), inside the staging copy, and the removal is
#: committed with the run or not at all (transaction.py) -- which is the whole migration, run by the
#: same `tools/re-produce.sh` an engine already runs after every overlay edit.
#:
#: They are not a fourth class: a retired path matches no row of TABLE, is written by nothing and is
#: hashed nowhere. The list exists so that *deleting* one is still recognisably the factory's work --
#: the engine's `tools/pr-policy.py` reads it, so a migration produce is not read as somebody's own
#: decision smuggled into a produce update. A pattern is never removed from this list, for the same
#: reason a recipe version is never removed: an engine that has not been produced since still holds
#: the files.
#:
#: **A pattern is not a licence to delete.** Every retirement is authorised by the bytes and never
#: by the path, and there are two ways to authorise one:
#:
#:   * `witness=WROTE_IT` (the default, #243): the engine's own `provenance.json` -- the record as
#:     it stood before this run -- hashed that exact path with those exact bytes in `generated` or
#:     `managed`. A file the record does not name, or one whose bytes have moved since it did, is
#:     somebody's: it is left where it is and named in the run's output. `backlog/notes.md`,
#:     written by hand and never emitted, matches `backlog/*.md` and is not the factory's to remove.
#:   * `witness=<a name in WITNESSES>` (#247): the record cannot speak for this file, and something
#:     else can. `corpus-map.overlay.json` is the engine's own evidence, which the factory never
#:     wrote and so cannot claim to have written: it is recorded in `buildInputs`, which says only
#:     which bytes were there. What retires it is not that the factory is dropping it but that this
#:     run **moved** it, into `overlay/<entry id>.json`, so the witness parses the bytes it is about
#:     to delete and requires the files beside it to carry every one of their keys and values
#:     (overlay.superseded_by_split). The bar is the same: prove, from the bytes, that deleting them
#:     takes nothing away.
#:
#: Both answers land in the same place -- deleted, or kept and named -- and the engine's
#: `tools/pr-policy.py` asks the same question of the base commit's bytes before admitting the
#: deletion into a produce update, so the run and the policy cannot disagree about who owned a file.
#:
#: **And a pattern may not overlap a row.** `retired_conflicts()` is checked before any deletion and
#: by the tests: no RETIRED pattern may be able to match a path any row of TABLE can match, so a
#: retirement can never reach an engine-owned or managed file -- adopted ones included -- however the
#: pattern is spelled. Overlap is decided **exactly**, inside the narrow grammar `RETIRED_SEGMENT`
#: admits and `check_retired_grammar` enforces, so the guard neither blocks a safe retirement nor
#: misses an unsafe one. That is the structural guard; the record check above is the second, and an
#: adopted file is listed in `engineOwned` without a hash, so it fails that one too.
#:
#: **A file kept once is kept for good.** The next `produce` writes a record that does not mention
#: it, so no later run can attribute it to the factory either. That is the trade this makes
#: deliberately: preserving a file somebody wrote, forever, costs an engine one path nothing
#: maintains, and the run names it every time; deleting it costs somebody their work.
RETIRED = (
    Retired("backlog/*.md",
            "the backlog is a projection of the map and the overlay -- filed as GitHub issues by "
            "`factory backlog --create`, printed by `factory backlog --render` -- and is not "
            "committed into an engine (#243)",
            WROTE_IT),
    Retired(overlay.RETIRED_NAME,
            f"the overlay is one file per entry, {overlay.DIRECTORY}/<entry id>{overlay.SUFFIX}, so that two "
            f"entry branches never write the same file; this run split it, and every key it held is in the "
            f"files beside it (#247)",
            "overlay-split"),
)

# Every version of every managed recipe: path -> {recipe version: SHA-256 of the bytes it wrote}.
# Version 1 of each is what the write-once scaffold wrote before #72. Never remove a version: an
# engine still carrying those bytes is unedited, and is migrated rather than refused.
RECIPE_SHA256 = {
    ".claude/agents/engine-dev.md": {
        1: "22dbac892b04903992d13516e5a08ac04d92d02b0d8d4ce5e4bfa9ef53543287",
        2: "5f0dd905e2b3857115d93196a66a168e17b505f87dda13a7d200f2bc12572bdb",
        3: "c8569477e58633f6e807a4b9be9a00b37a6f315d5b0f1fa8b0a7bc1f36b24b06",
        4: "f2b21c791a783f828f8d4dc3fa17407f6557a15923be9b0b67ce5a94ba69f926",
        5: "3491f1a0bbdd6b4fcb7b0d1e8d3827dfe5f4a19199d8da6ddcdc2b5bc9921521",
        6: "5e88a1d896a9f9528f038f6daffb990e03bdcfe5f9d39f60c88723c8ee8247ca",
        7: "8f26f1270af1eeaa12f471018cb8bf590265c573d690954b8cb942f64315746b",
        8: "d7838a14be85667f9f97e5a483be681a4a3a2ae969399aa7437762631639cc7c",
        9: "9bb4c07be9a29dd45b6e6d2e7ea96be95fa7227c9fbb20ea8251b21aaed6b693",
    },
    ".claude/agents/repo-steward.md": {
        1: "6a2662ac958da76bb02263914d4e3b293a8dc15837e8a6ffccb14177b013bde7",
    },
    ".claude/agents/rules-conformance.md": {
        1: "95eac2e802b474bdefad5a6053528dceda7465bbacfc946a0dd3c52a09705e78",
        2: "034cc0af3ecb98e9af60a65931102c69546f22ddadfea9c82961bb71fbbf96c2",
        3: "7f91ed4187d6d87621873266741f972a5b9bc8a27e16a248e78eb4de69789a64",
        4: "4f63b9d3336f708c76fbe1cc9ab1b73a62ffd4c382419a4f979ca0329ffd4c8d",
    },
    ".claude/hooks/primary-checkout-guard.py": {
        1: "a263531db502dfad98b38bf1dd90df7b1bec5f22133db016b6f30dc38509d16d",
    },
    ".claude/settings.json": {
        1: "4d410acd10ba5b6ed2d3c6a016cc2cfde1cf8e621da54424755376a80da30aa0",
    },
    "AGENTS.md": {
        1: "06594a3207634553a28ca057ecb53225082e4f111890961e27589c544353e740",
        2: "81f5756c1bff7ca2f1f9091087138fed0204a43e2f30a1e6f05ad4430e2efd48",
        3: "c3576d1cea769505a43794b8f2d42797f230f058b238eda09230f1fd3105ab50",
        4: "b615fbea821a0171f3b7cdc503da561a7f385504da48395fa1efef934c0fc833",
        5: "0bf3bb0f7519ac6cdccf4c03fd11bf65d8b3c0a4e5580917dd5bc7e8f81b1257",
        6: "7da4642b702c6a8f527b043e4cf1d8f54f5ac6efc8840df250e998c40ac152c3",
        7: "d141aa496491ab4eb6702fbdba803f82a4a0e11163c56289be404d9a7eeea8d9",
        8: "0dca04ff9fd39143f1d241c4f02d14dd54576524c9596e76539a5572a552be14",
        9: "64a111b943a7eb632f9d0bbd9ec065e4ddb6e7df625944b923c100da6871251f",
        10: "956af7bde2aaa84131f1dc88402d8f16a90715325c01381cafe626c97b187664",
        11: "721a114e68f56017c2c1319c2ea6202cf3af5bdef2eb9351f8fc088e333b6d50",
        12: "7a3bc27f251ff1a274838e5e55cb546392138dd675d668c4d94bf2173d2fb8a5",
        13: "151fe700348b37cf59f6fb4bbab5ef57dff7e41c0f080c0f78d4fbe4ab2dc011",
        14: "1e3f3666d4812f88e9cd24347c96794c7d7115bfbd2af78c8bceb30bfbb8fb8d",
        15: "5727dbd594baaace84cd5fa650eb9ec0e7d1779b4fd4bb262f74f3ccf56fb67b",
        16: "07c9b6a26199f3bf9b06db4ab308fbc4747dfe71b3e2ab17a4f637be67fe14f6",
        17: "f0148606dbd2a1e4f0614480ab74e7fa361876b9b65407019075f7a15dc24702",
        18: "2b6a2f95c659e0d17b524f2b401f32cfe047ebe0a7249bda05ba0b4e7bab61b5",
        19: "50c0496e6b4eb008dd649d3ca50af82400c6778b0fc1180cc3ec6d14aa2157c8",
    },
    "CLAUDE.md": {
        1: "04c07ad36e742fa60efafeca54d20bd96d16b6e338a44e46fad2b679ab8dfd9f",
    },
    "docs/agent-team.md": {
        1: "48baa22a5f1b6bb3f26d6aaed5715782462430b8b5524e1f0737ad627fae219d",
        2: "2972f4cdb30b4549639dc34de2fd47b8b06e0c680ef41e88de701ccfa66abb4d",
        3: "ae9c54d7236adca8507e673d77b51e6431a48f4a3c29af40d7420ea2810e8521",
        4: "1806e2679578deb3f6b59c920e1c209fb5c5606f36a07d1b8b9a942994103379",
        5: "f7f114fc7b8a74239a2f5fba97aadf69d5252e7683aa6061a5f9052c7b981689",
    },
    "tools/dispatch-agent.sh": {
        1: "868ce983b51d784a83a6a0fcac7456608b31f0af025c75ac5eeac64a373dca2b",
        2: "5e66ff9229bf31ed43d4a70c957e774696462dba3ff4e7f75b566132a6858cb5",
        3: "0f62f797181512f7e7e2b5b2314faaf50566866509f882927879e9361a7b6bfc",
        4: "a9f9d81b4fb2386acaa07f905f81f0848e02b6a93351aedc1f5a978f9225ca70",
    },
    "tools/new-issue.sh": {
        1: "382a2f516f81f593e74ed9e57262080c25edbac1a16d542ffb235eb772b10e88",
        2: "2830ba6458df4c34378538d73eadc4d522fb5f5cb7dbb945ef89097d66c9b9ee",
    },
    "tools/entry-packet.py": {
        1: "6e413d4e4143d888e00c1570358c5f6c7404347a173cd023b821f4d2f781835a",
        2: "59f112154a77a8cf574bd8d1ee1e43d39399025308c8f4eb2371d99081e49b20",
        3: "58791e5a923a50c591ef35325a7f45ec8db652f1b09179f5fc28c874b44d230f",
        4: "5ae5e226e92b0f1fe6ce227d58db2987173659d644e4a89667a984c9faee54af",
        5: "3ef75a792934d473e87db94e1c3f08f459bab418a73ef5850dd6063fa4144fad",
        6: "1125002f832f0876085db34be69de8701a43a5762ae31d49921d530c079ea0b0",
    },
    "tools/mutate.py": {
        1: "d33f7ddedc923388af4582ffb6c04a1434c09f695738ca34f191839f21847901",
    },
    "tools/re-produce.sh": {
        1: "2a281f94f81ce141733494a94744caa96c88af3cd9fa848cec21c13e73739499",
        2: "259e860a06e1407b38ff2f302bd657056eb601955e5363b19d30b705f74b7d8e",
        3: "0b0fd08926db78dff21bb8687e3cf57d34ff3a0456ae4cfb9ec1734ea2f8638f",
        4: "465fb02b0fafd06106cfef3f1e8d0858b4cee232f7f57dc8ac628fe6f7513a67",
        5: "4533319092ce21ccdcaaeade46dd4f10cdfa2209bb6f565efe0e9d163ef0b185",
        6: "27f0459e33e943fb7c6cd185b808f52ffa7165a7de44f267adbcd8654ce65262",
    },
    "tools/review-packet.py": {
        1: "2e989c02c1827bf6d3da8fce9a35874e25ea4baf14f62eeb64aab78c30b1f392",
        2: "7dc52854df87a7837deb0cb7373258e4f7516ad23a9984b7ee20813eefbc5d50",
        3: "5aa2d79176eea614b082653946c8ad48783dc2e8dc3966ae5b5894e83246f59e",
        4: "bc80949e2aa1a788ed72f9574ebe85846646200fb574a5cafa451f67bc08b2a9",
        5: "ccedcf96e26a8005387d2f95d7634b09196d1374db10a30b856a4375eeb49e1b",
        6: "445377e001ec8f17a881f7369e82eacb9ecf9646a87d225ea80022efef98d2d5",
        7: "7aa09461a5229497fedd360ec47cd05c8279e369be59626ef7a634caeb0d00ee",
    },
    "tools/pr-policy.py": {
        1: "79a33c7fe1ea8d888e4d6912a43ac60afe285c7a8bf43fbe9f7be87d6947b76e",
        2: "4a0c6677913decb13c8e9499840d5da4935c1725559dd6514d67dd72c8d849bd",
        3: "fc3ca4f9571e3276b7208a5927cdcef01da852ae97972a5c47663fe7391703eb",
        4: "1100f4005be978240ddd1f4ddb5001fefae8a89dff85818784dfe2e54ff61f8f",
        5: "c17dbf45d593454342680dc2b8333c88028ce9ec23367bdc668e8204202d4dc1",
        6: "308cbb15d1d908bc8db2c326633bd3ff7da97cc9447c057ba63fd81cc3574db5",
        7: "0606f6993cb2667b79788f8c4a0356e2d2e86dab12603628759ac906d1ed7941",
    },
    "tools/record-verdict.py": {
        1: "48f7b11f7fc829cdaebd776a3eb5db04e27cade97c427c6806b72f58805d83db",
        2: "befcec43518715bf0604f182b2edea5dea340f4979adfd6d49072a3b50184f84",
        3: "678b501239f684946dccbb6186035a39b5916257f0b3dadf13d35e6be97739a5",
    },
    "tools/conformance-gate.py": {
        1: "567972b60f16d1f86c661e97efa56fa2878c9a5aa92fb820c4aea07a402cbd24",
        2: "6e4a57468144caf4eaf74dce4d178a582322235ba37eb04d92bd72ddb929e58a",
        3: "ed0db727f1ac5500be0496bc42351d19faa353f3fc578b6d195e0b41cc23c634",
    },
    "tools/requeue-gate.py": {
        1: "a4315a5fa76a696ee616e5ef190d6bbec0d023c04e22086082d4031c460aec8d",
        2: "df937ba5ee305f52097406fa556c98ad0a98d4e6f76bb4a554ce0802fae1e952",
    },
    ".github/pull_request_template.md": {
        1: "e2cebc6419d62e2df3b218d76462caf807d6637f2b305ac2aa11153f13304a92",
        2: "8b679be11d7a53d3df4ee29fa687bff03042da01efa46a639da1d70e5dfe4234",
        3: "89a364ba817959aa0c3842b1fa3a9138df39d2dccd9f59f04ba33ce90d064f71",
        4: "3c21dc914830df9656fb49ec5cd56cbb56542f8121a219395cfc7d13f08aab74",
    },
    ".github/workflows/pr-policy.yml": {
        1: "caa3394a473d5fdd45b274176d8e28c48d9f5425176318194ba68fbea8453fa2",
    },
    ".github/workflows/conformance-gate.yml": {
        1: "851d64e8705363b70711b74fe1b25306c3fac1c1e26c88a9805defc3a03042a8",
        2: "d66ae8a37a37874369ac962fbecbf9ac1b98cf0246541a61ea5089b23f8ea702",
    },
    ".github/workflows/verdict-requeue.yml": {
        1: "b1a48c75587dcbcf15638f83a703025c08f5449d9e2611550c4f15a448fcb178",
        2: "8ab0d0de2df9777f3e545fedb66c118816e3c658a0fce87db63261967332780a",
    },
    "tools/agent-doctor.py": {
        1: "1b6fced99797d165ab0216523bddae183d6e7254f41d5d5f51cdb1d1c3b8913d",
        2: "340004575c29918f4dcbdacc7c1aef7f970e60bb270832901ae501bcb61b0b30",
        3: "1ae43e922fbbe2cdcd4e1ed2708ac7377d644d7cdfac63a95cda2d37d7ef276b",
        4: "4af176ea1850a69a148973f301a12ef6dafbd125ecc3d3bd4afff5c8581709f6",
        5: "48192fc3bfea14393824f39b049c73606631f07db8caecdf8107f2500bd18af6",
        6: "29a12d22a4befe577fcf67ab1ae868f0c1db3bc41d4d32babd812dd547324ab0",
    },
    ".editorconfig": {
        1: "4109d1ef55053ef656e536d7818934deb73016fbe950f153bae6b2a163591cb2",
    },
    "global.json": {
        1: "12f1cf1c3eef038f55de570dc8f5e321f4ff5306a9281106c43cc60a1f78a371",
    },
    "NuGet.config": {
        1: "b6475c7eb5334ba07f88ad900e82da0ebda9f269733c1c09237a72796c8d77f2",
        2: "e53f00efe0e550fb452b2e1d8d3b1e2f0cdd1de86628eff7d60a813ebfa1818f",
    },
    "Directory.Build.props": {
        1: "1392b57192cfe16ac70aa847f932c52f136765c9ce60ed94254d73dafd0d14ef",
        2: "73c373b1457e4149eb7ab7da1aed49314536ca8945dea8022c1efbd49c7a1a8f",
    },
}


class OwnershipError(Exception):
    """A managed file cannot be written without discarding an edit, or a flag names no managed file."""


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def rows(name):
    """TABLE with `{name}` replaced by the engine name."""
    return tuple(row._replace(pattern=row.pattern.replace("{name}", name)) for row in TABLE)


def _matches(pattern, relative):
    wanted, parts = pattern.split("/"), relative.split("/")
    return len(wanted) == len(parts) and all(fnmatch.fnmatchcase(p, w) for p, w in zip(parts, wanted))


def matching(relative, name):
    """Every row of the table that `relative` (an engine-relative POSIX path) matches."""
    return [row for row in rows(name) if _matches(row.pattern, relative)]


def classify(relative, name):
    """The one row `relative` matches, or None when it matches none. More than one is a table bug."""
    found = matching(relative, name)
    if len(found) > 1:
        raise OwnershipError(f"{relative} matches {len(found)} rows of the ownership table "
                             f"({', '.join(r.pattern for r in found)}); it must match exactly one")
    return found[0] if found else None


def managed_rows(name):
    return [row for row in rows(name) if row.cls == MANAGED]


def retired(relative, name):
    """The RETIRED entry `relative` matches, or None: a file `produce` used to write and now removes."""
    for row in RETIRED:
        if _matches(row.pattern.replace("{name}", name), relative):
            return row
    return None


#: The whole grammar a RETIRED pattern's segments may use. Each segment is a literal, or `*`, or
#: `*` followed by a literal suffix (`*.md`, `*.g.cs`). Nothing else: no `?`, no `[`, no interior or
#: trailing `*`, no `{name}`. The grammar is narrow on purpose -- inside it `_segments_can_overlap`
#: decides overlap **exactly**, so `retired_conflicts()` neither blocks a safe retirement nor misses
#: an unsafe one. `a*.md` and `*b.md` both match `ab.md` while neither matches the other, which is
#: the shape a fnmatch-both-ways test gets wrong; it is not in the grammar, so it cannot arise.
RETIRED_SEGMENT = re.compile(r"\A(?:\*[^*?\[\]{}]*|[^*?\[\]{}]+)\Z")


def _suffix(segment):
    """(is a glob, its literal suffix) for a segment in the grammar; None for one outside it."""
    if not RETIRED_SEGMENT.match(segment):
        return None
    return (True, segment[1:]) if segment.startswith("*") else (False, segment)


def _segments_can_overlap(one, other):
    """Whether two path segments could both match one segment. Exact inside the grammar.

    `one` is a retired segment, always in the grammar (`check_retired_grammar`). `other` is a
    table row's, with `{name}` already replaced by `*`: the engine name is one segment's worth of
    text, so `{name}.slnx` is exactly "anything, then `.slnx`" -- which is why a retirement of
    `obsolete.md` does not collide with it. A table segment outside the grammar (none is today)
    answers True, which refuses a retirement rather than admitting one on an answer this cannot
    give.
    """
    left, right = _suffix(one), _suffix(other)
    if left is None or right is None:
        return True
    (left_glob, left_text), (right_glob, right_text) = left, right
    if not left_glob and not right_glob:
        return left_text == right_text
    if not left_glob:
        return fnmatch.fnmatchcase(left_text, other)
    if not right_glob:
        return fnmatch.fnmatchcase(right_text, one)
    # Both are `*` plus a suffix: a witness exists exactly when one suffix ends the other.
    return left_text.endswith(right_text) or right_text.endswith(left_text)


def check_retired_grammar():
    """Refuse any RETIRED pattern outside the grammar overlap detection is exact for."""
    for gone in RETIRED:
        outside = [part for part in gone.pattern.split("/") if _suffix(part) is None]
        if outside:
            raise OwnershipError(
                f"the retired pattern {gone.pattern} uses {', '.join(repr(p) for p in outside)}, which is "
                f"outside the grammar a retirement may use (a literal, `*`, or `*` and a literal suffix). "
                f"Overlap with the ownership table is only decidable inside it, and a retirement whose "
                f"reach cannot be decided is not run")


def retired_conflicts():
    """[(retired pattern, row pattern)] that could both match one path: a table bug, always empty.

    A retirement deletes files. A pattern that could reach a row of TABLE could delete a generated,
    managed, adopted or engine-owned file -- the overlay, a lock file, a project -- so this makes
    that impossible rather than unlikely. Either the segment counts differ, or some segment pair is
    disjoint, or the pattern does not go in RETIRED.
    """
    check_retired_grammar()
    found = []
    for gone in RETIRED:
        for row in TABLE:
            left = gone.pattern.split("/")
            right = row.pattern.replace("{name}", "*").split("/")
            if len(left) == len(right) and all(_segments_can_overlap(a, b) for a, b in zip(left, right)):
                found.append((gone.pattern, row.pattern))
    return found


def _recorded_hashes(out):
    """{path: sha256} for every file `out`'s provenance.json says the factory wrote, or {}.

    `generated` and `managed` only: those are the two sections that say "the factory wrote these
    bytes". `engineOwned` says the opposite and carries no hash, and `buildInputs` says only which
    bytes were there. An unreadable or absent record yields {}, which makes `remove_retired` delete
    nothing -- the safe direction, since the alternative is deleting a file on no evidence.
    """
    try:
        with open(os.path.join(out, PROVENANCE), encoding="utf-8") as handle:
            return _hashes_of(json.load(handle))
    except (OSError, ValueError, AttributeError, TypeError):
        return {}


def _hashes_of(record):
    """The same, for a record already in hand (the engine's pr-policy.py has the base commit's)."""
    found = {}
    if not isinstance(record, dict):
        return found
    for section in (GENERATED, MANAGED):
        for item in record.get(section) or []:
            if isinstance(item, dict) and isinstance(item.get("path"), str) \
                    and isinstance(item.get("sha256"), str):
                found[item["path"]] = item["sha256"]
    return found


def _unauthorised(root, relative, data, row, recorded):
    """Why `data` at `relative` may not be deleted under retirement `row`, or None: the one line.

    `recorded` is `_recorded_hashes` of the record as it stood before the run. Both the remover and
    the engine's `tools/pr-policy.py` come through here (the policy via `authorised`), so a
    deletion the run makes and a deletion the policy admits are decided by the same sentence.
    """
    if row.witness is WROTE_IT:
        if relative not in recorded:
            return f"{PROVENANCE} does not record the factory as having written it"
        if sha256(data) != recorded[relative]:
            return (f"its bytes are not the ones {PROVENANCE} recorded ({recorded[relative][:12]}...), so it "
                    f"was edited after the last produce")
        return None
    witness = WITNESSES.get(row.witness)
    if witness is None:
        raise OwnershipError(f"the retired pattern {row.pattern} names the witness {row.witness!r}, which is "
                             f"not one of {', '.join(sorted(WITNESSES))}; a deletion nothing can authorise "
                             f"is not made")
    return witness(root, relative, data)


def authorised(root, relative, data, name, record):
    """Whether `data`, the bytes at retired `relative`, may be deleted. None-safe for `record`.

    The engine's `tools/pr-policy.py` calls this on the base commit's bytes, with the base commit's
    record, to decide whether a deletion in a pull request is the factory's own work. It is the
    remover's own test and not a second copy of it.
    """
    row = retired(relative, name)
    if row is None:
        return False
    return _unauthorised(root, relative, data, row, _hashes_of(record)) is None


def remove_retired(out, name):
    """Delete the files under `out` that a RETIRED pattern matches **and the record says are ours**.

    Returns `(removed, kept)`: the relative paths deleted, sorted, and `[(path, why)]` for every
    match left where it is. Run by `produce` in the staging copy before provenance is written, so
    the deletions are part of the one transaction and a refused run removes nothing; `out`'s
    provenance.json is still the record the engine had when the run began, which is what says who
    wrote each file.

    Matching the pattern is necessary and not sufficient; what makes it sufficient is the row's
    witness (RETIRED above). With `WROTE_IT`, a match is deleted only when that record hashed it in
    `generated` or `managed` **and** the bytes on disk are still that hash. So `backlog/notes.md`,
    written by hand under a directory the factory used to own, and an item file somebody edited
    after the last produce, are both kept -- and returned in `kept`, for the caller to print,
    because a file the factory has stopped maintaining and will not remove is something its owner
    should be told about rather than left to find. With a named witness, the record is not asked and
    the witness is: `corpus-map.overlay.json` goes only when `overlay/` carries every key it holds
    (#247), and an overlay that says anything those files do not is kept and named in exactly the
    same way.

    The bytes are re-hashed rather than trusted from the record, so an edited provenance.json cannot
    talk this into deleting a file: `recipe_versions` does not trust the record either, and for the
    same reason. The witness reads the bytes for the same reason again. Deletion by pathname alone
    was the first version of this and was wrong.

    A directory left empty by the deletions goes too; a directory holding anything else stays, with
    whatever else is in it.
    """
    conflicts = retired_conflicts()
    if conflicts:
        raise OwnershipError(
            "a retired pattern can match a path the ownership table owns, so a migration could delete a "
            "generated, managed, adopted or engine-owned file: "
            + "; ".join(f"{gone} overlaps {row}" for gone, row in conflicts))
    recorded = _recorded_hashes(out)
    removed, kept, directories = [], [], set()
    for directory, dirs, names in os.walk(out):
        dirs[:] = [d for d in dirs if d not in ("bin", "obj", ".git", ".vs")]
        for base in sorted(names):
            path = os.path.join(directory, base)
            relative = os.path.relpath(path, out).replace(os.sep, "/")
            row = retired(relative, name)
            if row is None:
                continue
            with open(path, "rb") as handle:
                data = handle.read()
            why = _unauthorised(out, relative, data, row, recorded)
            if why is not None:
                kept.append((relative, why))
                continue
            os.remove(path)
            removed.append(relative)
            directories.add(directory)
    for directory in sorted(directories, key=len, reverse=True):
        if directory != out and os.path.isdir(directory) and not os.listdir(directory):
            os.rmdir(directory)
    return sorted(removed), sorted(kept)


def adopted(out):
    """Managed paths the engine's provenance.json records as adopted (engine-owned).

    An unreadable or absent record adopts nothing. That is the safe direction: an adopted file
    that has been edited is then refused, naming --adopt, rather than overwritten.
    """
    try:
        with open(os.path.join(out, PROVENANCE), encoding="utf-8") as handle:
            record = json.load(handle)
        items = record.get("engineOwned") or []
        return {item["path"] for item in items if isinstance(item, dict) and item.get("adopted") is True
                and isinstance(item.get("path"), str)}
    except (OSError, ValueError, AttributeError, TypeError, KeyError):
        return set()


def recipe_versions(path, data):
    """Every recipe version of managed `path` whose bytes are `data`: empty for a hand edit."""
    digest = sha256(data)
    return [version for version, recorded in RECIPE_SHA256.get(path, {}).items() if recorded == digest]


# What `managed_states` finds a managed file to be.
ABSENT, CURRENT, EARLIER, ADOPTED, EDITED = "absent", "current", "earlier recipe", "adopted", "edited by hand"


def managed_states(out, paths):
    """What each managed file in `paths` is on disk in `out`, judged against the recipe history.

    Returns {path: (state, recipe versions its bytes are)}. `current` is the bytes of the table's
    recipe version; `earlier recipe` is the bytes of an older one, which the next `produce`
    migrates; `adopted` is a file provenance.json records as the engine's own, whatever its bytes;
    `edited by hand` is bytes no version of the recipe wrote, which `produce` refuses.

    It is the judgement `plan_managed` makes before a write, made without one, so that a report of
    the rails (`factory rails --check`, the engine's `tools/agent-doctor.py`) can say a rail is as
    the factory wrote it rather than only that a file of that name exists (#211).
    """
    table = {row.pattern: row for row in managed_rows("")}
    recorded = adopted(out)
    states = {}
    for path in sorted(paths):
        target = os.path.join(out, *path.split("/"))
        if not os.path.isfile(target):
            states[path] = (ABSENT, [])
            continue
        with open(target, "rb") as handle:
            versions = recipe_versions(path, handle.read())
        if path in recorded:
            states[path] = (ADOPTED, versions)
        elif not versions:
            states[path] = (EDITED, versions)
        elif path in table and table[path].recipe in versions:
            states[path] = (CURRENT, versions)
        else:
            states[path] = (EARLIER, versions)
    return states


def plan_managed(out, name, recipes, adopt=(), reset=()):
    """Decide every managed file for a run into `out`.

    `recipes` maps each managed path to the current recipe's bytes. Returns (writes, managed,
    adopted_now, notes): the bytes to write per path, {path: recipe version} for the files that
    stay managed, the set that is engine-owned by adoption, and a line per decision worth
    logging. Raises OwnershipError, before anything is written, for a flag that names no managed
    file and for every hand-edited managed file neither flag settles.
    """
    table = {row.pattern: row for row in managed_rows(name)}
    if set(recipes) != set(table):
        raise OwnershipError(f"the managed recipes ({sorted(recipes)}) are not the managed rows of the "
                             f"ownership table ({sorted(table)})")
    unknown = sorted(p for p in set(adopt) | set(reset) if p not in table)
    if unknown:
        raise OwnershipError(f"--adopt and --reset name managed files only ({', '.join(sorted(table))}); "
                             f"{', '.join(unknown)} is not one")
    both = sorted(set(adopt) & set(reset))
    if both:
        raise OwnershipError(f"{', '.join(both)} is given to both --adopt and --reset")
    recorded = adopted(out)
    writes, managed, adopted_now, notes, refused = {}, {}, set(), [], []
    for path, row in sorted(table.items()):
        target = os.path.join(out, *path.split("/"))
        current = recipes[path]
        if sha256(current) != RECIPE_SHA256.get(path, {}).get(row.recipe):
            raise OwnershipError(f"the {path} recipe's bytes are not recipe version {row.recipe}'s recorded "
                                 f"hash; a changed recipe needs a new version in the ownership table")
        on_disk = None
        if os.path.isfile(target):
            with open(target, "rb") as handle:
                on_disk = handle.read()
        if path in reset:
            writes[path] = current
            managed[path] = row.recipe
            notes.append(f"reset {path} to managed recipe {row.recipe}")
        elif path in adopt or path in recorded:
            adopted_now.add(path)
            if on_disk is None:
                writes[path] = current
            if path in adopt and path not in recorded:
                notes.append(f"adopted {path}: engine-owned from now on")
        elif on_disk is None:
            writes[path] = current
            managed[path] = row.recipe
        else:
            versions = recipe_versions(path, on_disk)
            if not versions:
                refused.append(path)
                continue
            managed[path] = row.recipe
            if on_disk != current:
                writes[path] = current
                notes.append(f"updated managed {path} from recipe {max(versions)} to {row.recipe}")
    if refused:
        raise OwnershipError(
            f"{', '.join(refused)} {'is a managed file' if len(refused) == 1 else 'are managed files'} "
            f"edited by hand: the bytes are no version of the factory's recipe, so produce will neither "
            f"overwrite the edit nor leave a stale policy unnoticed. Pass --adopt <path> to make it the "
            f"engine's own from now on, or --reset <path> to replace it with the current recipe")
    return writes, managed, adopted_now, notes
