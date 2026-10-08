"""The C# text of `ActionSurfaceAcceptance.g.cs` (decision 0078): the harness, and the structural
dump it compares final states with.

Kept apart from acceptance.py, which validates the declaration and assembles the file with the
structural dump, because the text is most of the size and the generator's modules are held to a size
(test_factory_modules.py). Nothing here reads a declaration; `acceptance.tests_cs` replaces the markers.
"""

HARNESS = """@HEADER@using System.Collections;
using System.Collections.Immutable;
using System.Globalization;
using System.Reflection;
using System.Text;
using RulesKernel.Provenance;
using RulesKernel.Resolution;
using Xunit;
using Xunit.Abstractions;

namespace @NAME@.Tests;

/// <summary>
/// The full-play acceptance of this engine's action surface (rules-factory decision 0078). Runs are
/// played from each configuration and seed, once per test run and in parallel; each fact holds one
/// invariant over the same runs. The engine implements the partial methods in its own adapter file;
/// without it this class does not build, and the compiler names each missing member.
/// </summary>
/// <remarks>
/// The adapter binds the engine's types with <c>global using ActionSurfaceState = ...;</c> and
/// <c>global using ActionSurfaceAction = ...;</c>. Nothing here applies a subset of the offered
/// actions: when a suite is too slow, make the engine faster.
/// </remarks>
public sealed partial class ActionSurfaceAcceptance
{
    /// <summary>How many seeds each configuration plays (<c>acceptance.json</c>).</summary>
    internal const int SeedsPerConfiguration = @SEEDS@;

    /// <summary>The most steps a run may take before it must be over (<c>acceptance.json</c>).</summary>
    internal const int StepCap = @CAP@;

    /// <summary>The fraction of a configuration's seeds that must reach a natural end (<c>acceptance.json</c>), exact.</summary>
    internal const decimal LeastCompleted = @LEAST@;

    /// <summary>The readings a run may end on: an entry id, and where the engine documents the reading.</summary>
    private static readonly (string EntryId, string Documented)[] Allowlist =
    [
@ALLOWLIST@    ];

    /// <summary>The stable names of the configurations a run starts from.</summary>
    /// <returns>The names, each non-blank and distinct.</returns>
    internal static partial ImmutableArray<string> Configurations();

    /// <summary>Starts a run from a configuration and a seed.</summary>
    /// <param name="configuration">One of <see cref="Configurations"/>.</param>
    /// <param name="seed">The seed of the run.</param>
    /// <returns>The state the run begins in.</returns>
    internal static partial ActionSurfaceState Start(string configuration, int seed);

    /// <summary>Whether a state is a natural end.</summary>
    /// <param name="state">A state. The call must not change it: no caching, no finalizing.</param>
    /// <returns>True when nothing more is to be done in it.</returns>
    internal static partial bool IsOver(ActionSurfaceState state);

    /// <summary>The actions legal in a state.</summary>
    /// <param name="state">A state that is not over. The call must not change it.</param>
    /// <returns>The offered actions, or an unresolved resolution saying why there are none.</returns>
    internal static partial Resolution<ImmutableArray<ActionSurfaceAction>> LegalActions(ActionSurfaceState state);

    /// <summary>Applies an action to a state.</summary>
    /// <param name="state">The state. The call must not change it.</param>
    /// <param name="action">An action <see cref="LegalActions"/> offered in it.</param>
    /// <returns>The new state, or an unresolved resolution for a refusal or a decline.</returns>
    internal static partial Resolution<ActionSurfaceState> Apply(ActionSurfaceState state, ActionSurfaceAction action);

    /// <summary>Renders an action as one line of a run's history.</summary>
    /// <param name="action">An action.</param>
    /// <returns>A line that is equal for equal actions and different for unequal ones.</returns>
    internal static partial string Render(ActionSurfaceAction action);

    private static readonly Lazy<HashSet<SourceLocator>> AllowedLocators =
        new(() => Allowlist.Select(item => Registry.Entry(item.EntryId).Locator).ToHashSet());

    private static readonly Lazy<Played> Everything = new(PlayEverything, LazyThreadSafetyMode.ExecutionAndPublication);

    private readonly ITestOutputHelper output;

    public ActionSurfaceAcceptance(ITestOutputHelper output) => this.output = output;

    // 1
    [Fact]
    public void Every_offered_action_is_accepted() =>
        Hold(1, "an offered action is refused or declined outside the allowlist, or a call changed the state it was given");

    // 2
    [Fact]
    public void Nothing_throws() =>
        Hold(2, "a call on the surface threw");

    // 3
    [Fact]
    public void Nothing_stalls_without_a_reason() =>
        Hold(3, "a state that is not over offers nothing and says nothing");

    // 4
    [Fact]
    public void A_run_ends_within_the_step_cap() =>
        Hold(4, "a run went past the step cap");

    // 5
    [Fact]
    public void Runs_stop_early_only_on_the_allowlist() =>
        Hold(5, "a run stopped on an unresolved answer that is not an allowlisted reading");

    // 6
    [Fact]
    public void Enough_runs_complete()
    {
        var problems = new List<string>(Everything.Value.Findings(6));
        var runs = Everything.Value.Runs;
        foreach (var configuration in Everything.Value.Configurations.Distinct())
        {
            var played = runs.Where(run => run.Configuration == configuration).ToList();
            if (played.Count == 0)
            {
                problems.Add($"{configuration}: no runs were played, and an empty configuration does not pass");
                continue;
            }

            var completed = played.Count(run => run.Completed);
            // In decimal, which holds the product exactly (the declaration has at most 18 places).
            if (!(completed >= LeastCompleted * played.Count))
            {
                problems.Add($"{configuration}: {completed} of {played.Count} seeds reached a natural end, below the declared {LeastCompleted.ToString(CultureInfo.InvariantCulture)}");
            }
        }

        if (Everything.Value.Configurations.Length == 0)
        {
            problems.Add("the surface offers no configuration, and nothing was played");
        }

        Assert.True(problems.Count == 0, Describe("too few runs completed", problems));
    }

    // 7
    [Fact]
    public void Replay_is_deterministic_compared_structurally()
    {
        var problems = new List<string>(Everything.Value.Findings(7));
        foreach (var (first, again) in Everything.Value.Replays)
        {
            var name = $"{first.Configuration} seed {first.Seed}";
            var at = Enumerable.Range(0, Math.Min(first.History.Count, again.History.Count))
                .Where(i => first.History[i] != again.History[i]).Select(i => (int?)i).FirstOrDefault();
            if (at is not null)
            {
                problems.Add($"{name}: the histories first differ at step {at}: '{first.History[at.Value]}' then '{again.History[at.Value]}'");
            }
            else if (first.History.Count != again.History.Count)
            {
                problems.Add($"{name}: the histories have {first.History.Count} and {again.History.Count} steps");
            }

            // The state at the start of every step, the last of them the state the run ended in, each
            // dumped when it was reached: a later call cannot have changed what is compared.
            var states = Enumerable.Range(0, Math.Min(first.Dumps.Count, again.Dumps.Count))
                .Where(i => first.Dumps[i] != again.Dumps[i]).Select(i => (int?)i).FirstOrDefault();
            if (states is not null)
            {
                var (left, right) = (first.Dumps[states.Value], again.Dumps[states.Value]);
                problems.Add($"{name}: the states first differ structurally at step {states}, from offset {StructuralDump.FirstDifference(left, right)}: {StructuralDump.Around(left, right)}");
            }
            else if (first.Dumps.Count != again.Dumps.Count)
            {
                problems.Add($"{name}: the runs dumped {first.Dumps.Count} and {again.Dumps.Count} states");
            }

            // The fields of each ending, framed as every state is: never the display string.
            var (ended, endedAgain) = (StructuralDump.Of(first.Ending), StructuralDump.Of(again.Ending));
            if (ended != endedAgain)
            {
                problems.Add($"{name}: the runs ended differently: '{first.Ending}' then '{again.Ending}' ({StructuralDump.Around(ended, endedAgain)})");
            }
        }

        Assert.True(problems.Count == 0, Describe("a replay did not reproduce, or two unequal actions render alike", problems));
    }

    // The locator a decline names is the item's, so a locator another entry cites would let one
    // documented decline excuse another.
    [Fact]
    public void Allowlisted_locators_are_cited_by_one_entry_only()
    {
        var problems = new List<string>();
        foreach (var (entryId, documented) in Allowlist)
        {
            var locator = Registry.Entry(entryId).Locator;
            var citing = Registry.Entries.Where(entry => entry.Id != entryId && entry.Locators.Contains(locator))
                .Select(entry => entry.Id).ToList();
            if (citing.Count > 0)
            {
                problems.Add($"{entryId} ({documented}): its locator is also cited by {string.Join(", ", citing)}");
            }
        }

        // Not a failure: the seeds of the gate may not reach a reading that a longer probe did. But the
        // list is built from declines that were observed, so an item no run reached is named.
        var reached = Everything.Value.Reached();
        foreach (var (entryId, documented) in Allowlist.Where(item => !reached.Contains(Registry.Entry(item.EntryId).Locator)))
        {
            output.WriteLine($"{entryId} ({documented}): no run declined at this reading, in {Everything.Value.Runs.Count + Everything.Value.Replays.Count} runs");
        }

        Assert.True(problems.Count == 0, Describe("an allowlisted locator is shared", problems));
    }

    private static void Hold(int invariant, string what)
    {
        var problems = Everything.Value.Findings(invariant);
        Assert.True(problems.Count == 0, Describe(what, problems));
    }

    private static string Describe(string what, IReadOnlyList<string> problems) =>
        $"{what}: {problems.Count} finding(s)" + string.Concat(problems.Take(12).Select(p => "\\n  - " + p))
        + (problems.Count > 12 ? $"\\n  ... and {problems.Count - 12} more" : "");

    private static Played PlayEverything()
    {
        var played = new Played();
        try
        {
            played.Configurations = Configurations();
        }
        catch (Exception error)
        {
            played.Setup(2, $"Configurations() threw {Where(error)}");
        }

        if (played.Configurations.IsDefault)
        {
            played.Configurations = [];
        }

        if (played.Configurations.Any(string.IsNullOrWhiteSpace) || played.Configurations.Distinct().Count() != played.Configurations.Length)
        {
            played.Setup(6, "the configurations are not stable names: one is blank or two are equal");
        }

        var plan = played.Configurations.Distinct().Where(c => !string.IsNullOrWhiteSpace(c))
            .SelectMany(c => Enumerable.Range(0, SeedsPerConfiguration).Select(seed => (Configuration: c, Seed: seed))).ToList();
        var runs = new Run[plan.Count];
        Parallel.For(0, plan.Count, i => runs[i] = Play(plan[i].Configuration, plan[i].Seed, plan[i].Seed == 0));
        played.Runs = runs;

        var firsts = runs.Where(run => run.Seed == 0).ToList();
        var again = new Run[firsts.Count];
        Parallel.For(0, firsts.Count, i => again[i] = Play(firsts[i].Configuration, firsts[i].Seed, true));
        played.Replays = firsts.Zip(again).ToList();
        return played;
    }

    // A capturing run dumps the state at the start of every step, and again after each call that must
    // not change it. It is on for each configuration's first seed and its replay, which bounds the
    // cost: a dump walks the whole state.
    private static Run Play(string configuration, int seed, bool capture)
    {
        var run = new Run(configuration, seed, capture);
        ActionSurfaceState state;
        try
        {
            state = Start(configuration, seed);
        }
        catch (Exception error)
        {
            run.Threw("Start", error);
            return run.Stop(Ending.Invariant(2, "Start threw"));
        }

        string? returned = null;
        for (var step = 0; ; step++)
        {
            var before = run.Dump(state);
            if (before is not null)
            {
                if (returned is not null && returned != before)
                {
                    run.Find(1, $"{run.Name} step {step}: the state the chosen action returned was changed by a later call on the step before: {StructuralDump.Around(returned, before)}");
                }

                run.Begin(before);
            }

            bool over;
            try
            {
                over = IsOver(state);
            }
            catch (Exception error)
            {
                run.Threw($"IsOver at step {step}", error);
                return run.Stop(Ending.Invariant(2, "IsOver threw"));
            }

            // The run's last dump is the one above, so a lazily finalizing IsOver is compared here.
            run.After(state, step, "IsOver");
            if (over)
            {
                run.Completed = true;
                return run.Stop(Ending.Completed());
            }

            if (step >= StepCap)
            {
                run.Find(4, $"{run.Name}: not over after {StepCap} steps");
                return run.Stop(Ending.Invariant(4, "not over within the step cap"));
            }

            Resolution<ImmutableArray<ActionSurfaceAction>> legal;
            try
            {
                legal = LegalActions(state);
            }
            catch (Exception error)
            {
                run.Threw($"LegalActions at step {step}", error);
                return run.Stop(Ending.Invariant(2, "LegalActions threw"));
            }

            run.After(state, step, "LegalActions");
            var (offered, declined) = legal.Match(
                actions => (Offered: actions, Declined: (UnresolvedResult?)null),
                result => (Offered: default(ImmutableArray<ActionSurfaceAction>), Declined: (UnresolvedResult?)result));
            if (declined is not null)
            {
                if (run.Allowed(declined))
                {
                    return run.Stop(Ending.Stopped(declined));
                }

                run.Find(5, $"{run.Name} step {step}: stopped on {Name(declined)}, which is not an allowlisted reading");
                return run.Stop(Ending.Invariant(5, declined));
            }

            if (offered.IsDefaultOrEmpty)
            {
                run.Find(3, $"{run.Name} step {step}: the state is not over, offers no action and gives no reason");
                return run.Stop(Ending.Invariant(3, "offers nothing and says nothing"));
            }

            var lines = run.Lines(step, offered);
            var chosen = (int)(Mix(seed, step) % (ulong)offered.Length);

            // Before any outcome is resolved, so the step a run ends on is in its history.
            run.History.Add(lines[chosen]);
            Resolution<ActionSurfaceState>? advance = null;
            string? kept = null;
            for (var i = 0; i < offered.Length; i++)
            {
                Resolution<ActionSurfaceState> applied;
                try
                {
                    applied = Apply(state, offered[i]);
                }
                catch (Exception error)
                {
                    run.Threw($"Apply of offered action {i} at step {step}", error);
                    return run.Stop(Ending.Invariant(2, "Apply threw"));
                }

                if (i == chosen)
                {
                    // Exactly as returned: the probes that follow are applied to the same state, and
                    // must not reach this one.
                    advance = applied;
                    kept = applied.Match<string?>(value => run.Dump(value), _ => null);
                }

                run.After(state, step, $"Apply of offered action {i}");
                var refusal = applied.Match<UnresolvedResult?>(_ => null, unresolved => unresolved);
                if (refusal is not null && !run.Allowed(refusal))
                {
                    run.Find(1, $"{run.Name} step {step}: offered action {i} '{lines[i]}' was answered with {Name(refusal)}");
                }
            }

            var stopped = advance!.Match<UnresolvedResult?>(_ => null, unresolved => unresolved);
            if (stopped is not null)
            {
                return run.Stop(run.Allowed(stopped) ? Ending.Stopped(stopped) : Ending.Invariant(1, stopped));
            }

            state = advance.Match(value => value, _ => throw new InvalidOperationException("unreachable"));
            returned = kept;
        }
    }

    private static string Name(UnresolvedResult result) =>
        $"{result.Reason} at {result.Locator} ({result.Attempted})";

    /// <summary>How a run ended, as fields: replays are compared by their dump, never by a display string.</summary>
    internal sealed class Ending
    {
        private Ending(string kind, string? reason = null, string? sourceId = null, string? citation = null, string? attempted = null) =>
            (Kind, Reason, SourceId, Citation, Attempted) = (kind, reason, sourceId, citation, attempted);

        public string Kind { get; }

        public string? Reason { get; }

        public string? SourceId { get; }

        public string? Citation { get; }

        public string? Attempted { get; }

        public static Ending Completed() => new("completed");

        public static Ending Stopped(UnresolvedResult result) => Of("stopped", result);

        public static Ending Invariant(int invariant, string what) => new($"invariant {invariant} ({what})");

        public static Ending Invariant(int invariant, UnresolvedResult result) => Of($"invariant {invariant}", result);

        private static Ending Of(string kind, UnresolvedResult result) =>
            new(kind, result.Reason.ToString(), result.Locator.SourceId, result.Locator.Citation, result.Attempted);

        public override string ToString() => Reason is null ? Kind : $"{Kind}: {Reason} at {SourceId} {Citation} ({Attempted})";
    }

    private static string Where(Exception error)
    {
        var frame = (error.StackTrace ?? "").Split('\\n').Select(line => line.Trim()).FirstOrDefault(line => line.Length > 0);
        return $"{error.GetType().FullName}: {error.Message} [first frame: {frame ?? "none"}]";
    }

    // SplitMix64 over (seed, step): the choice depends on nothing but them, not on a hash code,
    // a culture or a clock.
    private static ulong Mix(int seed, int step)
    {
        unchecked
        {
            var z = (((ulong)(uint)seed << 32) | (uint)step) + 0x9E3779B97F4A7C15UL;
            z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9UL;
            z = (z ^ (z >> 27)) * 0x94D049BB133111EBUL;
            return z ^ (z >> 31);
        }
    }

    private sealed class Run(string configuration, int seed, bool capturing)
    {
        private readonly Dictionary<int, List<string>> findings = new();
        private string? seen;

        public string Configuration { get; } = configuration;

        public int Seed { get; } = seed;

        public string Name => $"{Configuration} seed {Seed}";

        public bool Completed { get; set; }

        /// <summary>How the run ended: completed; stopped on an allowlisted decline; or the invariant a finding stopped it under.</summary>
        public Ending Ending { get; private set; } = Ending.Invariant(0, "the run did not end");

        /// <summary>The rendered line of each action the run chose, the one it ended on included.</summary>
        public List<string> History { get; } = [];

        /// <summary>The dump of the state at the start of each step, taken then (capturing runs only).</summary>
        public List<string> Dumps { get; } = [];

        /// <summary>The locators of the allowlisted declines the run met.</summary>
        public HashSet<SourceLocator> Reached { get; } = [];

        public Run Stop(Ending ending)
        {
            Ending = ending;
            return this;
        }

        public IReadOnlyList<string> Of(int invariant) =>
            findings.TryGetValue(invariant, out var list) ? list : [];

        public void Find(int invariant, string text)
        {
            if (!findings.TryGetValue(invariant, out var list))
            {
                findings[invariant] = list = [];
            }

            list.Add(text);
        }

        public void Threw(string call, Exception error) => Find(2, $"{Name}: {call} threw {Where(error)}");

        public bool Allowed(UnresolvedResult result)
        {
            var allowed = result.Reason == UnresolvedReason.RequiresInterpretation && AllowedLocators.Value.Contains(result.Locator);
            if (allowed)
            {
                Reached.Add(result.Locator);
            }

            return allowed;
        }

        /// <summary>The dump of a state, as it is now; null when the run does not capture, or the state cannot be dumped.</summary>
        public string? Dump(object? state)
        {
            if (!capturing)
            {
                return null;
            }

            try
            {
                return StructuralDump.Of(state);
            }
            catch (Exception error)
            {
                capturing = false;
                Find(7, $"{Name}: a state cannot be dumped ({error.GetType().Name}: {error.Message})");
                return null;
            }
        }

        public void Begin(string dump)
        {
            seen = dump;
            Dumps.Add(dump);
        }

        /// <summary>Invariant 1: a call on the surface must leave the state it was given as it was.</summary>
        public void After(ActionSurfaceState state, int step, string call)
        {
            var now = seen is null ? null : Dump(state);
            if (seen is not null && now is not null && now != seen)
            {
                Find(1, $"{Name} step {step}: {call} changed the state it was given: {StructuralDump.Around(seen, now)}");
                seen = now;
            }
        }

        /// <summary>Renders every offered action; two unequal ones with one line are a finding under invariant 7.</summary>
        public string[] Lines(int step, ImmutableArray<ActionSurfaceAction> offered)
        {
            var lines = new string[offered.Length];
            var first = new Dictionary<string, int>();
            var reported = false;
            for (var i = 0; i < offered.Length; i++)
            {
                lines[i] = Line(offered[i]);
                if (!first.TryAdd(lines[i], i) && !reported && !Equals(offered[first[lines[i]]], offered[i]))
                {
                    reported = true;
                    Find(7, $"{Name} step {step}: offered actions {first[lines[i]]} and {i} are not equal and both render as '{lines[i]}'");
                }
            }

            return lines;
        }

        private string Line(ActionSurfaceAction action)
        {
            try
            {
                return Render(action);
            }
            catch (Exception error)
            {
                Threw("Render", error);
                return "<Render threw>";
            }
        }
    }

    private sealed class Played
    {
        private readonly Dictionary<int, List<string>> setup = new();

        public ImmutableArray<string> Configurations { get; set; }

        public IReadOnlyList<Run> Runs { get; set; } = [];

        public IReadOnlyList<(Run First, Run Again)> Replays { get; set; } = [];

        public void Setup(int invariant, string text)
        {
            if (!setup.TryGetValue(invariant, out var list))
            {
                setup[invariant] = list = [];
            }

            list.Add(text);
        }

        public IReadOnlyList<string> Findings(int invariant) =>
            (setup.TryGetValue(invariant, out var own) ? own : [])
            .Concat(Runs.SelectMany(run => run.Of(invariant)))
            .Concat(Replays.SelectMany(pair => pair.Again.Of(invariant).Select(text => "(replay) " + text)))
            .ToList();

        public HashSet<SourceLocator> Reached() =>
            Runs.Concat(Replays.Select(pair => pair.Again)).SelectMany(run => run.Reached).ToHashSet();
    }

@DUMP@
}
"""
