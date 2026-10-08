// The adapter of a toy action surface, for tests/factory/test_factory_acceptance.py (decision 0078).
// It is a fixture: a counter that offers +1 and +2 and is over at 10 or more, written against the
// HoyleBackgammon engine that scripts/validate-engine.sh produces. The test copies it, with the
// engine's name, to tests/HoyleBackgammon.Tests/ActionSurface.cs, which is where an engine's own
// adapter lives and which `produce` never writes.
//
// One build serves every case: the environment variable ACTION_SURFACE_FIXTURE names the violation
// to commit, so each invariant is shown red without a rebuild per case. Each violation happens only in
// the runs `Affected` names, so the others still complete and the one invariant under test is the only
// one broken.
global using ActionSurfaceState = HoyleBackgammon.Tests.Counter;
global using ActionSurfaceAction = HoyleBackgammon.Tests.Step;

using System.Collections.Immutable;
using RulesKernel.Resolution;

namespace HoyleBackgammon.Tests;

/// <summary>A toy state. Not a record, and equal by <see cref="Value"/> alone, as a record that
/// compares its collections by reference would be: its equality cannot tell two replays apart.</summary>
public sealed class Counter : IEquatable<Counter>
{
    private readonly int stamp;

    public Counter(string configuration, int seed, int value, ImmutableArray<int> trail, int stamp)
    {
        Configuration = configuration;
        Seed = seed;
        Value = value;
        Trail = trail;
        this.stamp = stamp;
    }

    public string Configuration { get; }

    public int Seed { get; }

    public int Value { get; }

    public ImmutableArray<int> Trail { get; }

    public ImmutableArray<int> NeverSet { get; }

    public ImmutableDictionary<string, int> Tally { get; init; } = ImmutableDictionary<string, int>.Empty;

    public ImmutableHashSet<int> Seen { get; init; } = [];

    public Func<int> Ignored { get; init; } = () => 0;

    public int Stamp() => stamp;

    public Counter Next(int by, int stampNow) =>
        new(Configuration, Seed, Value + by, Trail.Add(by), stampNow)
        {
            Tally = Tally.SetItem(by.ToString(), Tally.GetValueOrDefault(by.ToString()) + 1),
            Seen = Seen.Add(by),
        };

    public bool Equals(Counter? other) => other is not null && Value == other.Value;

    public override bool Equals(object? obj) => Equals(obj as Counter);

    public override int GetHashCode() => Value;
}

public readonly record struct Step(int By);

public sealed class FixtureEquality
{
    // What the structural dump is for: this state's equality cannot see a private field, so two
    // replays that differ only in it are "equal" to everything but the dump.
    [Xunit.Fact]
    public void Equality_cannot_see_a_private_field()
    {
        var one = new Counter("alpha", 0, 10, [], stamp: 1);
        var other = new Counter("alpha", 0, 10, [], stamp: 2);
        Xunit.Assert.Equal(one, other);
        Xunit.Assert.NotEqual(one.Stamp(), other.Stamp());
    }
}

public sealed partial class ActionSurfaceAcceptance
{
    private static readonly string Variant = Environment.GetEnvironmentVariable("ACTION_SURFACE_FIXTURE") ?? "correct";

    private static int stamps;

    // The runs a violation is committed in: a quarter of the alpha configuration's seeds, so the
    // completion fraction the fixture declares still holds.
    private static bool Affected(Counter state) => state.Configuration == "alpha" && state.Seed % 4 == 0 && state.Value >= 6;

    // What the engine's registry answers for an entry it has not built: UnsupportedRule, a refusal.
    private static Resolution<T> Refusal<T>(string entryId) =>
        Registry.Resolve(entryId, RuleRequest.Empty)
            .Match(_ => throw new InvalidOperationException(entryId + " resolved; the fixture needs a declined entry"),
                   Resolution<T>.FromUnresolved);

    // A reading left open: RequiresInterpretation, at the locator of the entry that documents it.
    private static Resolution<T> Open<T>(string entryId, UnresolvedReason reason = UnresolvedReason.RequiresInterpretation) =>
        Resolution<T>.FromUnresolved(new UnresolvedResult(reason, "the fixture leaves " + entryId + " open", Registry.Entry(entryId).Locator));

    internal static partial ImmutableArray<string> Configurations() => ["alpha", "beta"];

    internal static partial Counter Start(string configuration, int seed) =>
        new(configuration, seed, configuration == "alpha" ? 0 : 4, [],
            Variant == "drift" ? Interlocked.Increment(ref stamps) : 0);

    internal static partial bool IsOver(Counter state) => state.Value >= 10;

    internal static partial Resolution<ImmutableArray<Step>> LegalActions(Counter state)
    {
        if (Variant == "throw" && Affected(state))
        {
            throw new InvalidOperationException("the fixture throws here");
        }

        if (Variant == "stall" && Affected(state))
        {
            return Resolution<ImmutableArray<Step>>.FromValue([]);
        }

        if (Variant == "decline-outside" && Affected(state))
        {
            return Open<ImmutableArray<Step>>("must-play-whole-throw");
        }

        if (Variant == "decline-reason" && Affected(state))
        {
            return Open<ImmutableArray<Step>>("rubber-scoring", UnresolvedReason.OutsideCurrentScope);
        }

        if ((Variant == "decline-allowed" && Affected(state)) || (Variant == "slow" && state.Configuration == "beta"))
        {
            return Open<ImmutableArray<Step>>("rubber-scoring");
        }

        return Resolution<ImmutableArray<Step>>.FromValue([new Step(1), new Step(2)]);
    }

    internal static partial Resolution<Counter> Apply(Counter state, Step action)
    {
        if (Variant == "refuse" && Affected(state) && action.By == 2)
        {
            return Refusal<Counter>("player-count");
        }

        if (Variant == "loop" && Affected(state))
        {
            return Resolution<Counter>.FromValue(state.Next(action.By - state.Value, state.Stamp()));
        }

        return Resolution<Counter>.FromValue(state.Next(action.By, state.Stamp()));
    }

    internal static partial string Render(Step action) =>
        $"+{action.By}" + (Variant == "history-drift" ? "#" + Interlocked.Increment(ref stamps) : "");
}
