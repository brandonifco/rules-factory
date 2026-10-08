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

    /// <summary>The fraction of a configuration's seeds that must reach a natural end (<c>acceptance.json</c>).</summary>
    internal const double LeastCompleted = @LEAST@;

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
    /// <param name="state">A state.</param>
    /// <returns>True when nothing more is to be done in it.</returns>
    internal static partial bool IsOver(ActionSurfaceState state);

    /// <summary>The actions legal in a state.</summary>
    /// <param name="state">A state that is not over.</param>
    /// <returns>The offered actions, or an unresolved resolution saying why there are none.</returns>
    internal static partial Resolution<ImmutableArray<ActionSurfaceAction>> LegalActions(ActionSurfaceState state);

    /// <summary>Applies an action to a state.</summary>
    /// <param name="state">The state.</param>
    /// <param name="action">An action <see cref="LegalActions"/> offered in it.</param>
    /// <returns>The new state, or an unresolved resolution for a refusal or a decline.</returns>
    internal static partial Resolution<ActionSurfaceState> Apply(ActionSurfaceState state, ActionSurfaceAction action);

    /// <summary>Renders an action as one line of a run's history.</summary>
    /// <param name="action">An action.</param>
    /// <returns>A line that is equal for equal actions.</returns>
    internal static partial string Render(ActionSurfaceAction action);

    private static readonly Lazy<HashSet<SourceLocator>> AllowedLocators =
        new(() => Allowlist.Select(item => Registry.Entry(item.EntryId).Locator).ToHashSet());

    private static readonly Lazy<Played> Everything = new(PlayEverything, LazyThreadSafetyMode.ExecutionAndPublication);

    // 1
    [Fact]
    public void Every_offered_action_is_accepted() =>
        Hold(1, "an offered action is refused or declined outside the allowlist");

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
            if ((double)completed / played.Count < LeastCompleted)
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
            var at = Enumerable.Range(0, Math.Min(first.History.Count, again.History.Count))
                .Where(i => first.History[i] != again.History[i]).Select(i => (int?)i).FirstOrDefault();
            if (at is not null)
            {
                problems.Add($"{first.Configuration} seed {first.Seed}: the histories first differ at step {at}: '{first.History[at.Value]}' then '{again.History[at.Value]}'");
            }
            else if (first.History.Count != again.History.Count)
            {
                problems.Add($"{first.Configuration} seed {first.Seed}: the histories have {first.History.Count} and {again.History.Count} steps");
            }

            try
            {
                var left = StructuralDump.Of(first.Final);
                var right = StructuralDump.Of(again.Final);
                if (left != right)
                {
                    problems.Add($"{first.Configuration} seed {first.Seed}: the final states differ structurally, from offset {StructuralDump.FirstDifference(left, right)}: {StructuralDump.Around(left, right)}");
                }
            }
            catch (Exception error)
            {
                problems.Add($"{first.Configuration} seed {first.Seed}: the final state cannot be dumped ({error.GetType().Name}: {error.Message})");
            }
        }

        Assert.True(problems.Count == 0, Describe("a replay did not reproduce", problems));
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
        Parallel.For(0, plan.Count, i => runs[i] = Play(plan[i].Configuration, plan[i].Seed));
        played.Runs = runs;

        var firsts = runs.Where(run => run.Seed == 0).ToList();
        var again = new Run[firsts.Count];
        Parallel.For(0, firsts.Count, i => again[i] = Play(firsts[i].Configuration, firsts[i].Seed));
        played.Replays = firsts.Zip(again).ToList();
        return played;
    }

    private static Run Play(string configuration, int seed)
    {
        var run = new Run(configuration, seed);
        ActionSurfaceState state;
        try
        {
            state = Start(configuration, seed);
        }
        catch (Exception error)
        {
            run.Threw("Start", error);
            return run;
        }

        run.Final = state;
        for (var step = 0; ; step++)
        {
            bool over;
            try
            {
                over = IsOver(state);
            }
            catch (Exception error)
            {
                run.Threw($"IsOver at step {step}", error);
                return run;
            }

            if (over)
            {
                run.Completed = true;
                return run;
            }

            if (step >= StepCap)
            {
                run.Find(4, $"{run.Name}: not over after {StepCap} steps");
                return run;
            }

            Resolution<ImmutableArray<ActionSurfaceAction>> legal;
            try
            {
                legal = LegalActions(state);
            }
            catch (Exception error)
            {
                run.Threw($"LegalActions at step {step}", error);
                return run;
            }

            var (offered, declined) = legal.Match(
                actions => (Offered: actions, Declined: (UnresolvedResult?)null),
                result => (Offered: default(ImmutableArray<ActionSurfaceAction>), Declined: (UnresolvedResult?)result));
            if (declined is not null)
            {
                if (!Allowed(declined))
                {
                    run.Find(5, $"{run.Name} step {step}: stopped on {Name(declined)}, which is not an allowlisted reading");
                }

                return run;
            }

            if (offered.IsDefaultOrEmpty)
            {
                run.Find(3, $"{run.Name} step {step}: the state is not over, offers no action and gives no reason");
                return run;
            }

            var chosen = (int)(Mix(seed, step) % (ulong)offered.Length);
            Resolution<ActionSurfaceState>? advance = null;
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
                    return run;
                }

                if (i == chosen)
                {
                    advance = applied;
                }

                var refusal = applied.Match<UnresolvedResult?>(_ => null, result => result);
                if (refusal is not null && !Allowed(refusal))
                {
                    run.Find(1, $"{run.Name} step {step}: offered action {i} '{run.Line(offered[i])}' was answered with {Name(refusal)}");
                }
            }

            if (!advance!.IsResolved)
            {
                return run;
            }

            var next = advance.Match(value => value, _ => throw new InvalidOperationException("unreachable"));
            run.History.Add(run.Line(offered[chosen]));
            state = next;
            run.Final = state;
        }
    }

    private static bool Allowed(UnresolvedResult result) =>
        result.Reason == UnresolvedReason.RequiresInterpretation && AllowedLocators.Value.Contains(result.Locator);

    private static string Name(UnresolvedResult result) =>
        $"{result.Reason} at {result.Locator} ({result.Attempted})";

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

    private sealed class Run(string configuration, int seed)
    {
        private readonly Dictionary<int, List<string>> findings = new();

        public string Configuration { get; } = configuration;

        public int Seed { get; } = seed;

        public string Name => $"{Configuration} seed {Seed}";

        public bool Completed { get; set; }

        public object? Final { get; set; }

        public List<string> History { get; } = [];

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

        public string Line(ActionSurfaceAction action)
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
    }

@DUMP@
}
"""
